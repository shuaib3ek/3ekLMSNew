from flask import render_template, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.workshops.models import Learner, WorkshopRegistration

from . import learners_bp

@learners_bp.before_request
@login_required
def require_admin():
    if current_user.role not in ['admin', 'super_admin']:
        abort(403)

@learners_bp.route('/')
def list_learners():
    """
    Global Learner Roster.
    Fetches all unique learners and their associated workshop registrations.
    """
    # Eager load registrations and their associated workshops to prevent N+1 query problems
    all_learners = Learner.query.options(
        joinedload(Learner.registrations).joinedload(WorkshopRegistration.workshop)
    ).order_by(Learner.created_at.desc()).all()
    
    return render_template('learners/list.html', learners=all_learners)
