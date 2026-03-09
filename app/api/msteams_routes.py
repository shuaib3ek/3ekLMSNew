from flask import Blueprint, request, jsonify, current_app

msteams_bp = Blueprint('msteams', __name__)


def _verify_service_token():
    token = request.headers.get('X-Service-Token', '')
    expected = current_app.config.get('LMS_SERVICE_TOKEN', '')
    return token == expected


@msteams_bp.route('/notifications', methods=['POST'])
def teams_notifications():
    """Receive MS Graph change notifications for Teams meeting recordings."""
    # Validation token handshake (required by MS Graph on subscription)
    validation_token = request.args.get('validationToken')
    if validation_token:
        return validation_token, 200, {'Content-Type': 'text/plain'}

    data = request.get_json(silent=True) or {}
    # Process incoming notification (recording ready, etc.)
    # Full implementation to be ported from 3EK-Pulse app/api/msteams_routes.py
    current_app.logger.info(f'[LMS] Teams notification received: {data}')
    return jsonify({'status': 'accepted'}), 202
