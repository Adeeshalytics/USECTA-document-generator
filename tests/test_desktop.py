import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from docx import Document
from streamlit.testing.v1 import AppTest

import documents
from documents import Store
from workflows import prepare_workspace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('usb_copy', ROOT / 'scripts/make-usb-copy.py')
usb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb)


def test_desktop_ignores_cloud_secrets_and_never_contacts_supabase(tmp_path, monkeypatch):
    from cloud_store import SupabaseAPI
    monkeypatch.setenv('USECTA_LOCAL_MODE', '1')
    store = Store(tmp_path)
    monkeypatch.setattr(documents, 'Store', lambda: store)
    def reject(*args, **kwargs):
        raise AssertionError('Local app contacted Supabase')
    monkeypatch.setattr(SupabaseAPI, 'request', reject)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.secrets.update({'STORAGE_BACKEND': 'supabase', 'SUPABASE_URL': 'https://example.supabase.co',
                        'SUPABASE_SECRET_KEY': 'do-not-send', 'SUPABASE_PUBLISHABLE_KEY': 'do-not-send',
                        'ALLOWED_EMAILS': ['owner@example.com']})
    app.run()
    assert not app.exception
    assert len(app.tabs) == 5
    assert len(store.catalog('SPMC/03/2026')) == 50
    assert not any(button.label == 'Sign in' for button in app.button)
    app.text_input(key='supplier_new_supplier_name').set_value('Saved while offline')
    next(button for button in app.button if button.label == 'Save supplier').click().run()
    assert not app.exception
    assert any(row['supplier_name'] == 'Saved while offline' for row in Store(tmp_path).suppliers().values())


@pytest.fixture
def prepared_folder(tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir()
    for name in usb.FILES:
        shutil.copy2(ROOT / name, folder / name)
    (folder / 'scripts').mkdir()
    for name in usb.SCRIPTS:
        shutil.copy2(ROOT / 'scripts' / name, folder / 'scripts' / name)
    for name in ['company_templates', 'catalogues']:
        shutil.copytree(ROOT / name, folder / name)
    for name in ['python', 'libreoffice']:
        (folder / 'runtime' / name).mkdir(parents=True)
        (folder / 'runtime' / name / 'example-runtime-file').write_text('bundled component')
    (folder / 'runtime/ready.txt').write_text('prepared')
    (folder / 'runtime/downloads').mkdir()
    (folder / 'runtime/downloads/not-for-sharing').write_text('large installer')
    (folder / '.streamlit').mkdir()
    (folder / '.streamlit/secrets.toml').write_text('SUPABASE_SECRET_KEY="private"')
    (folder / '.git').mkdir()
    store = Store(folder / 'data')
    prepare_workspace(store, folder)
    store.save_supplier({'supplier_name': 'Private supplier'})
    store.save_catalog('SPMC/03/2026', [{'item_number': '15', 'description': 'Our edited item', 'document_fee': '500'}])
    store.save_record('Original run', {'supplier_name': 'Private supplier'})
    (folder / 'data/desktop-session.json').write_text('{"token":"private session"}')
    (folder / 'data/desktop.log').write_text('private log')
    return folder


def test_pendrive_copy_retains_snapshot_and_excludes_secrets(prepared_folder, tmp_path):
    destination = tmp_path / 'Director copy with spaces'
    usb.assemble(prepared_folder, destination, include_data=True)
    assert not (destination / '.streamlit').exists()
    assert not (destination / '.git').exists()
    assert not (destination / 'runtime/downloads').exists()
    assert not (destination / 'data/desktop-session.json').exists()
    assert not (destination / 'data/desktop.log').exists()
    moved = tmp_path / 'Moved to another PC'
    destination.rename(moved)
    store = Store(moved / 'data')
    assert store.catalog('SPMC/03/2026')[0]['description'] == 'Our edited item'
    assert list(store.suppliers().values())[0]['supplier_name'] == 'Private supplier'
    assert json.loads(store.records()[0]['payload'])['supplier_name'] == 'Private supplier'
    for template in store.templates():
        assert store.template_path(template).read_bytes()
    store.save_supplier({'supplier_name': 'Director adds supplier'})
    assert len(Store(prepared_folder / 'data').suppliers()) == 1


def test_fresh_usb_copy_contains_no_personal_workspace(prepared_folder, tmp_path):
    destination = tmp_path / 'Fresh'
    usb.assemble(prepared_folder, destination)
    assert not (destination / 'data').exists()
    store = Store(destination / 'data')
    prepare_workspace(store, destination)
    assert store.suppliers() == {}
    assert store.records() == []
    assert len(store.catalog('SPMC/03/2026')) == 50
    assert len(store.templates()) == 7
    with pytest.raises(ValueError, match='never overwritten'):
        usb.assemble(prepared_folder, destination, include_data=True)
    assert store.records() == []


def test_windows_libreoffice_detection_without_path(tmp_path, monkeypatch):
    monkeypatch.delenv('USECTA_PDF_EXECUTABLE', raising=False)
    monkeypatch.setattr(documents, 'DATA_DIR', tmp_path / 'data')
    folder = tmp_path / 'Program Files'
    exe = folder / 'LibreOffice/program/soffice.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'placeholder')
    monkeypatch.setenv('ProgramFiles', str(folder))
    monkeypatch.setattr(documents.shutil, 'which', lambda name: None)
    assert documents.pdf_available() == str(exe)


@pytest.mark.skipif(not documents.pdf_available() or not shutil.which('pdftotext'), reason='LibreOffice and pdftotext needed')
def test_batch_pdf_preserves_each_document_and_uses_one_process(monkeypatch, tmp_path):
    files = {}
    for name in ['FIRST DOCUMENT', 'SECOND DOCUMENT']:
        doc = Document()
        doc.add_paragraph(name)
        output = io.BytesIO()
        doc.save(output)
        files[name + '.docx'] = output.getvalue()
    real_run = documents.subprocess.run
    calls = []
    def record(command, **kwargs):
        calls.append(command)
        return real_run(command, **kwargs)
    monkeypatch.setattr(documents.subprocess, 'run', record)
    pdfs = documents.convert_pdfs(files)
    assert len(calls) == 1
    assert len(pdfs) == 2
    for name in ['FIRST DOCUMENT', 'SECOND DOCUMENT']:
        pdf = tmp_path / (name + '.pdf')
        pdf.write_bytes(pdfs[pdf.name])
        text = real_run(['pdftotext', str(pdf), '-'], capture_output=True, check=True, text=True).stdout
        assert name in text
        assert ('SECOND DOCUMENT' if name == 'FIRST DOCUMENT' else 'FIRST DOCUMENT') not in text
