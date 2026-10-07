"""Cloud configuration and company login, evaluated before accessing records."""
import time

import streamlit as st

from cloud_store import SupabaseAPI, SupabaseStore
import documents


def workspace_store():
    try:
        settings = dict(st.secrets)
    except FileNotFoundError:
        settings = {}
    backend = settings.get('STORAGE_BACKEND', 'local')
    if backend == 'local':
        return documents.Store(), False
    if backend != 'supabase':
        st.error('STORAGE_BACKEND must be local or supabase.')
        st.stop()
    required = ['SUPABASE_URL', 'SUPABASE_SECRET_KEY', 'SUPABASE_PUBLISHABLE_KEY', 'ALLOWED_EMAILS']
    if any(not settings.get(key) for key in required):
        st.error('Cloud setup is incomplete. Add the required credentials and approved emails in Streamlit Secrets. See CLOUD_DEPLOYMENT.md.')
        st.stop()
    emails = settings['ALLOWED_EMAILS']
    if not isinstance(emails, list) or any(not isinstance(email, str) for email in emails):
        st.error('ALLOWED_EMAILS must be a list of company email addresses.')
        st.stop()
    allowed = {email.strip().lower() for email in emails if email.strip()}
    if not allowed:
        st.error('Configure at least one approved company email.')
        st.stop()
    session = st.session_state.get('company_login')
    if session and (session['expires_at'] <= time.time() or session['email'] not in allowed):
        st.session_state.clear()
        session = None
    if not session:
        st.title('USECTA sign in')
        with st.form('company_signin'):
            email = st.text_input('Email').strip().lower()
            password = st.text_input('Password', type='password')
            submitted = st.form_submit_button('Sign in')
        if submitted:
            if email not in allowed:
                st.error('Sign-in failed. Check your credentials and approved company email.')
            else:
                try:
                    public_api = SupabaseAPI(settings['SUPABASE_URL'], settings['SUPABASE_PUBLISHABLE_KEY'])
                    result = public_api.request('POST', '/auth/v1/token?grant_type=password', {'email': email, 'password': password})
                    user_email = result.get('user', {}).get('email', '').lower()
                    if user_email != email or not result.get('access_token'):
                        raise RuntimeError('Invalid sign-in response.')
                    # Tokens/passwords are not retained. Reauthentication is required on expiry.
                    st.session_state['company_login'] = {'email': email, 'expires_at': time.time() + min(int(result.get('expires_in', 3600)), 3600)}
                    st.rerun()
                except (RuntimeError, ValueError, KeyError):
                    st.error('Sign-in failed. Check your credentials and approved company email.')
        st.stop()
    with st.sidebar:
        st.caption('Signed in as ' + session['email'])
        if st.button('Sign out'):
            st.session_state.clear()
            st.rerun()
    api = SupabaseAPI(settings['SUPABASE_URL'], settings['SUPABASE_SECRET_KEY'])
    return SupabaseStore(api), True
