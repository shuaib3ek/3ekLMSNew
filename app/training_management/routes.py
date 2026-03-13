from flask import render_template, abort
from flask_login import login_required, current_user
from . import training_bp
from app.crm_client.client import fetch_pulse_programs

@training_bp.before_request
@login_required
def require_admin():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)

@training_bp.route('/')
def list_pulse_programs():
    """Fetches read-only historical program data from 3ek-pulse."""
    programs = fetch_pulse_programs()
    return render_template('training_management/list.html', programs=programs)
