from flask import render_template, abort
from flask_login import login_required, current_user
from . import admin_bp
from app.workshops.models import Workshop

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)

@admin_bp.route('/dashboard')
def dashboard():
    # Gather high-level metrics for the Enterprise Air Traffic Control view
    active_workshops_count = Workshop.query.filter(Workshop.status.in_(['published', 'draft'])).count()
    completed_workshops_count = Workshop.query.filter_by(status='completed').count()
    
    # For Phase 1, we pass basic numbers. Next phases will populate advanced ATC health metrics.
    return render_template(
        'admin/dashboard.html',
        active_workshops_count=active_workshops_count,
        completed_workshops_count=completed_workshops_count
    )
