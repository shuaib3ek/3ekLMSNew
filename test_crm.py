from app import create_app
from app.crm_client.client import fetch_pulse_programs, get_open_requests

app = create_app()
with app.app_context():
    programs = fetch_pulse_programs()
    print("PROGRAM SAMPLE:", programs[0] if programs else None)
    reqs = get_open_requests(1) # Try with client id 1
    print("REQUEST SAMPLE:", reqs[0] if reqs else None)
