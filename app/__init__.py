"""
3EK LMS — Flask App Factory
Completely independent from 3EK-Pulse (CRM).
Cross-references to CRM (Users, Clients, Contacts, Trainers) go through
app/crm_client/client.py via HTTP only — never via direct DB access or imports.
"""
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from .core.extensions import db, csrf, login_manager
from flask_wtf.csrf import CSRFError
from config import Config
from .core import shadow_models # Register shadow tables


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS for mobile / learner API access
    CORS(app)

    # CSRF protection
    csrf.init_app(app)

    # Login Manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from flask import session
        from app.auth.models import StaffUser

        # Non-admin roles (learner, trainer, client):
        # their full user_data is cached in the session under '_lms_user'
        # so we don't need a CRM round-trip and don't lose the role.
        cached = session.get('_lms_user')
        if cached and str(cached.get('id')) == str(user_id):
            return StaffUser(cached)

        # Admin: resolve via CRM API
        from app.crm_client import get_user
        user_data = get_user(user_id)
        if user_data:
            return StaffUser(user_data)

        return None


    # Proxy fix for HTTPS behind Nginx
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Allow Jinja2 'do' extension
    app.jinja_env.add_extension('jinja2.ext.do')

    # Initialise database
    db.init_app(app)

    # Flask-Migrate
    from flask_migrate import Migrate
    Migrate(app, db)

    # Background Scheduler (Teams recording poll & webhook renewal)
    try:
        from .core.scheduler import init_scheduler
        init_scheduler(app)
    except Exception as e:
        print(f'LMS Scheduler init failed (ignore during migrations): {e}')

    # ── Template Filters ────────────────────────────────────────────────────
    import json

    @app.template_filter('from_json')
    def from_json_filter(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except Exception:
            return []

    @app.context_processor
    def inject_globals():
        from datetime import date
        return dict(today=date.today())

    # ── Blueprints ───────────────────────────────────────────────────────────

    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Workshops (full ownership: create, manage, schedule, deliver, analyse)
    from .workshops import workshops_bp
    app.register_blueprint(workshops_bp, url_prefix='/workshops')
    # Public registration & confirmation are CSRF-exempt (no browser session)
    csrf.exempt('workshops.register_public')
    csrf.exempt('workshops.confirm_registration')
    csrf.exempt('workshops.payment_callback')

    # Learner REST API (JWT-authenticated, no CSRF)
    from .api.learner_routes import learner_bp
    app.register_blueprint(learner_bp, url_prefix='/api/v1/learner')
    csrf.exempt(learner_bp)

    # Learner Web Portal (OTP-authenticated, session-based)
    from .learner import learner_portal_bp
    app.register_blueprint(learner_portal_bp, url_prefix='/my')

    # Trainer Web Portal (OTP-authenticated, session-based)
    from .trainer import trainer_portal_bp
    app.register_blueprint(trainer_portal_bp, url_prefix='/trainer')

    # Client Web Portal (OTP-authenticated, session-based)
    from .client import client_portal_bp
    app.register_blueprint(client_portal_bp, url_prefix='/client')


    # MS Teams webhook receiver (server-to-server, no CSRF)
    from .api.msteams_routes import msteams_bp
    app.register_blueprint(msteams_bp, url_prefix='/api/v1/msteams')
    csrf.exempt(msteams_bp)

    # Internal LMS API (called by CRM with service token, no CSRF)
    from .api.internal_routes import internal_bp
    app.register_blueprint(internal_bp, url_prefix='/api/v1/lms')
    csrf.exempt(internal_bp)

    # Website-facing JSON API (called by 3ek-website Next.js, no CSRF)
    from .api.website_routes import website_bp
    app.register_blueprint(website_bp, url_prefix='/pulse-api')
    csrf.exempt(website_bp)

    # Admin Enterprise Portal (Metrics, Routing)
    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Training Management (Historical Pulse Data)
    from .training_management import training_bp
    app.register_blueprint(training_bp, url_prefix='/training_management')

    # Learners (Global Roster)
    from .learners import learners_bp
    app.register_blueprint(learners_bp, url_prefix='/learners')

    # ── Health Check ─────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.role in ['admin', 'super_admin']:
                return redirect(url_for('admin.dashboard'))
            elif current_user.role == 'trainer':
                return redirect(url_for('trainer_portal.dashboard'))
            elif current_user.role == 'client':
                return redirect(url_for('client_portal.dashboard'))
            else:
                return redirect(url_for('learner.dashboard'))
        return redirect(url_for('auth.login'))

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': '3ek-lms'})


    # ── Error Handlers ───────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.error(f"CSRF Error: {e.description}")
        # If it's an AJAX request, return JSON
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'X-CSRFToken' in request.headers:
            return jsonify({'error': f'CSRF token mismatch: {e.description}. Try refreshing the page.'}), 400
        return render_template('errors/400.html', message=f"CSRF Error: {e.description}. Please refresh and try again."), 400

    return app
