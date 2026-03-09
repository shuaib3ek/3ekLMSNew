"""
3EK LMS — Flask App Factory
Completely independent from 3EK-Pulse (CRM).
Cross-references to CRM (Users, Clients, Contacts, Trainers) go through
app/crm_client/client.py via HTTP only — never via direct DB access or imports.
"""
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from .core.extensions import db, csrf
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS for mobile / learner API access
    CORS(app)

    # CSRF protection
    csrf.init_app(app)

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

    # Workshops (full ownership: create, manage, schedule, deliver, analyse)
    from .workshops import workshops_bp
    app.register_blueprint(workshops_bp, url_prefix='/workshops')
    # Public registration & confirmation are CSRF-exempt (no browser session)
    csrf.exempt('workshops.register_public')
    csrf.exempt('workshops.confirm_registration')

    # Learner REST API (JWT-authenticated, no CSRF)
    from .api.learner_routes import learner_bp
    app.register_blueprint(learner_bp, url_prefix='/api/v1/learner')
    csrf.exempt(learner_bp)

    # MS Teams webhook receiver (server-to-server, no CSRF)
    from .api.msteams_routes import msteams_bp
    app.register_blueprint(msteams_bp, url_prefix='/api/v1/msteams')
    csrf.exempt(msteams_bp)

    # Internal LMS API (called by CRM with service token, no CSRF)
    from .api.internal_routes import internal_bp
    app.register_blueprint(internal_bp, url_prefix='/api/v1/lms')
    csrf.exempt(internal_bp)

    # ── Health Check ─────────────────────────────────────────────────────────
    from flask import jsonify

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': '3ek-lms'})

    # ── Error Handlers ───────────────────────────────────────────────────────
    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app
