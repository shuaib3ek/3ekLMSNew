from app import create_app
from app.core.extensions import db
from app.core.shadow_models import ShadowStaffUser
from flask import url_for
app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
with app.app_context():
    with app.test_client() as client:
        # Mock login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = '1'  # Assuming admin is ID 1
        
        # Test toggle route
        response = client.post('/training_management/64/toggle/assessments')
        print("Status Code:", response.status_code)
        print("Response Data:", response.data)
