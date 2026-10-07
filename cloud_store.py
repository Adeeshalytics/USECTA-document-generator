"""Server-side Supabase persistence; local files are only a disposable cache."""
import hashlib
import json
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from documents import FIELDS, COMPUTED, template_variables, validate_word


class SupabaseError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Supabase request failed (HTTP {status}). Check the cloud setup and credentials.")


class SupabaseAPI:
    def __init__(self, url, key):
        if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url.rstrip('/')):
            raise ValueError("Use your HTTPS Supabase project URL.")
        self.url, self.key = url.rstrip('/'), key

    def request(self, method, path, payload=None, raw=False, headers=None):
        data = payload if isinstance(payload, bytes) else (json.dumps(payload).encode() if payload is not None else None)
        request_headers = {"apikey": self.key, "Content-Type": "application/json"}
        # Legacy service_role JWTs also require a bearer header; new secret keys do not.
        if self.key.startswith('eyJ'):
            request_headers['Authorization'] = 'Bearer ' + self.key
        request_headers.update(headers or {})
        try:
            with urlopen(Request(self.url + path, data=data, headers=request_headers, method=method), timeout=30) as response:
                content = response.read()
        except HTTPError as exc:
            raise SupabaseError(exc.code) from None
        except (URLError, TimeoutError):
            raise RuntimeError("Cannot reach Supabase. Try again shortly.") from None
        return content if raw else (json.loads(content) if content else None)


class SupabaseStore:
    def __init__(self, api, bucket='document-templates', cache_root=None):
        self.api, self.bucket = api, bucket
        self.root = Path(cache_root or Path(tempfile.gettempdir()) / 'usecta-cloud-cache')
        self.templates_dir = self.root / 'templates'
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def _rows(self, kind, key=None):
        query = {'kind': 'eq.' + kind, 'select': 'key,data', 'order': 'key.asc', 'limit': '1000'}
        if key is not None:
            query['key'] = 'eq.' + key
        # Paginate saved history and metadata beyond PostgREST's default row limit.
        rows, offset = [], 0
        while True:
            query['offset'] = str(offset)
            page = self.api.request('GET', '/rest/v1/usecta_entries?' + urlencode(query))
            rows.extend(page)
            if len(page) < 1000:
                return rows
            offset += len(page)

    def _put(self, kind, key, data, insert=False):
        headers = {'Prefer': 'return=minimal' + ('' if insert else ',resolution=merge-duplicates')}
        self.api.request('POST', '/rest/v1/usecta_entries?on_conflict=kind,key',
                         {'kind': kind, 'key': key, 'data': data}, headers=headers)

    def profiles(self):
        return {r['key']: r['data'] for r in self._rows('profile')}

    def save_profile(self, name, payload):
        if not name.strip():
            raise ValueError('Give the profile a name.')
        self._put('profile', name.strip(), payload)

    def records(self):
        return sorted([r['data'] | {'payload': json.dumps(r['data']['payload'])} for r in self._rows('record')],
                      key=lambda r: r['created_at'], reverse=True)

    def save_record(self, name, payload):
        if not name.strip():
            raise ValueError('Give the project a name.')
        key = uuid.uuid4().hex
        self._put('record', key, {'id': key, 'name': name.strip(), 'payload': payload,
                                  'created_at': datetime.now(timezone.utc).isoformat()}, insert=True)
        return key

    def templates(self):
        return sorted([r['data'] for r in self._rows('template')], key=lambda r: r['name'])

    def template_path(self, template):
        name = template['filename']
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.docx', name):
            raise ValueError('Invalid stored template filename.')
        content = self.api.request('GET', '/storage/v1/object/authenticated/' + quote(self.bucket, safe='') + '/' + name, raw=True)
        digest = hashlib.sha256(content).hexdigest()
        path = self.templates_dir / (digest + '.docx')
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=self.templates_dir, delete=False) as output:
                output.write(content)
                temporary = Path(output.name)
            temporary.replace(path)
        return path

    def add_template(self, name, content, required=(), key=None, workflow='legacy', scope='batch'):
        if not name.strip():
            raise ValueError('Give the template a name.')
        validate_word(content)
        variables = template_variables(content)
        for field in variables - set(FIELDS) - COMPUTED:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', field):
                raise ValueError(f'Unsupported field name: {field}')
        if set(required) - variables:
            raise ValueError('Required fields must appear in the template.')
        key = key or uuid.uuid4().hex
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
            raise ValueError('Invalid template ID.')
        existing = self._rows('template', key)
        if existing:
            return key  # deterministic built-in seeds never replace an existing version
        filename = key + '.docx'
        try:
            self.api.request('POST', '/storage/v1/object/' + quote(self.bucket, safe='') + '/' + filename,
                             content, headers={'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'x-upsert': 'false'})
        except SupabaseError as exc:
            if exc.status not in (400, 409):
                raise
            # Recover a concurrent seed or an upload whose metadata save failed.
            stored = self.api.request('GET', '/storage/v1/object/authenticated/' + quote(self.bucket, safe='') + '/' + filename, raw=True)
            if stored != content:
                raise ValueError('This template version already contains different content.')
        metadata = {'id': key, 'name': name.strip(), 'filename': filename,
                    'required': list(required), 'created_at': datetime.now(timezone.utc).isoformat(),
                    'workflow': workflow, 'scope': scope}
        try:
            self._put('template', key, metadata, insert=True)
        except SupabaseError as exc:
            if exc.status != 409 or not self._rows('template', key):
                raise
        return key

    def set_template_usage(self, key, workflow, scope):
        if workflow not in {'legacy', 'tender', 'quotation'} or scope not in {'batch', 'item', 'supplier', 'tender'}:
            raise ValueError('Choose a supported document type and scope.')
        rows = self._rows('template', key)
        if not rows:
            raise ValueError('Template not found.')
        self._put('template', key, rows[0]['data'] | {'workflow': workflow, 'scope': scope})

    def tenders(self):
        return {r['key']: r['data'] for r in self._rows('tender')}

    def save_tender(self, reference, payload):
        from workflows import validate_tender
        reference = reference.strip()
        validate_tender(reference, payload)
        self._put('tender', reference, payload)

    def catalog(self, reference):
        rows = self._rows('catalog', reference)
        return sorted(rows[0]['data'] if rows else [], key=lambda r: (len(r['item_number']), r['item_number']))

    def save_catalog(self, reference, rows):
        from workflows import validate_catalog
        cleaned = validate_catalog(rows)
        if not self._rows('tender', reference):
            raise ValueError('Save this tender before adding its item catalogue.')
        # One database upsert replaces the whole catalogue atomically.
        self._put('catalog', reference, cleaned)

    def suppliers(self):
        return {r['key']: r['data'] for r in sorted(self._rows('supplier'), key=lambda r: r['data']['supplier_name'])}

    def save_supplier(self, payload, key=None):
        if not payload.get('supplier_name', '').strip():
            raise ValueError('Enter the supplier name.')
        key = key or uuid.uuid4().hex
        self._put('supplier', key, payload)
        return key
