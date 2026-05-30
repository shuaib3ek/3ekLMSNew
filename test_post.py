from app import create_app
import requests

app = create_app()
with app.app_context():
    pass
# wait, I can just use requests against localhost:8014 if I can get a session.
