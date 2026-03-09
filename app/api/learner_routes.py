from flask import Blueprint

learner_bp = Blueprint('learner', __name__)


@learner_bp.route('/ping')
def ping():
    from flask import jsonify
    return jsonify({'status': 'ok', 'service': 'lms-learner-api'})


# Additional learner routes (video progress, session list, etc.)
# will be ported from 3EK-Pulse app/api/learner_routes.py
# with all CRM model imports replaced by crm_client calls.
