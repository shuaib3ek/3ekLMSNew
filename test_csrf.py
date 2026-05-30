from app import create_app
from flask import url_for, g
app = create_app()
with app.app_context():
    with app.test_client() as client:
        # Get CSRF token
        response = client.get('/login')
        print(response.status_code)
