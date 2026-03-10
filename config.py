import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'lms-dev-secret-key-change-in-prod'

    # LMS Database — completely separate from CRM
    SQLALCHEMY_DATABASE_URI = os.environ.get('LMS_DATABASE_URL') or 'sqlite:///lms.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True
    WTF_CSRF_SSL_STRICT = False  # Allow HTTP for local dev
    WTF_CSRF_TIME_LIMIT = None  # Tokens last for the entire session
    
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_NAME = '3ek_lms_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    APP_NAME = '3EK LMS'
    THEME_COLOR = '#6366f1'

    # ─── CRM Cross-Reference (API only — no direct DB access) ───────────────────
    # The LMS never connects to the CRM database.
    # All shared entity lookups (Users, Clients, Contacts, Trainers) go through
    # the CRM internal REST API via app/crm_client/client.py.
    CRM_API_URL = os.environ.get('CRM_API_URL') or 'http://localhost:8013'
    CRM_SERVICE_TOKEN = os.environ.get('CRM_SERVICE_TOKEN')

    # Token that authorises incoming calls FROM the CRM to this LMS
    LMS_SERVICE_TOKEN = os.environ.get('LMS_SERVICE_TOKEN')

    # ─── Microsoft Graph (Teams integration) ────────────────────────────────────
    MS_CLIENT_ID = os.environ.get('MS_CLIENT_ID')
    MS_CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET')
    MS_TENANT_ID = os.environ.get('MS_TENANT_ID')
    MS_REDIRECT_URI = os.environ.get('MS_REDIRECT_URI')

    # ─── Storage ─────────────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(
        os.getcwd(), 'storage'
    )

    # ─── 3EK Course Studio API ───────────────────────────────────────────────────
    COURSE_API_URL = os.environ.get('COURSE_API_URL') or 'http://localhost:8010'

    # ─── Public Website ──────────────────────────────────────────────────────────
    WEBSITE_BASE_URL = os.environ.get('WEBSITE_BASE_URL') or 'https://www.3ek.in'
    BASE_URL = os.environ.get('BASE_URL') or 'https://lms.3ek.in'

    # ─── AI ──────────────────────────────────────────────────────────────────────
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

    # ─── Razorpay (paid workshop payments) ──────────────────────────────────────
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
