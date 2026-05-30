from app import create_app
from flask import url_for
app = create_app()
with app.app_context():
    with app.test_request_context():
        try:
            print("URL:", url_for('training_management.toggle_feature', crm_engagement_id=64, feature=''))
        except Exception as e:
            print("Error:", str(e))
