import requests
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

crm_url = os.environ.get('CRM_API_URL') or 'http://localhost:8013'
crm_token = os.environ.get('CRM_SERVICE_TOKEN')

print("--- 3EK LMS Connectivity Diagnostic ---")
print(f"Target CRM URL: {crm_url}")
print(f"Service Token Set: {'Yes' if crm_token else 'No'}")

print("\n1. Testing basic connectivity (GET /api/v1/crm/trainers)...")
try:
    headers = {'X-Service-Token': crm_token} if crm_token else {}
    # Use a simple endpoint that doesn't need many params
    response = requests.get(f"{crm_url}/api/v1/crm/trainers", headers=headers, timeout=5)
    print(f"Status Code: {response.status_code}")
    if response.ok:
        print("Success: CRM API is reachable!")
    else:
        print(f"Failure: CRM returned error: {response.text[:200]}")
except Exception as e:
    print(f"CRITICAL ERROR: Could not reach CRM. Error: {e}")
    print("\nPossible solutions:")
    print(f"- If running in Docker, 'localhost' might not work. Try using the bridge IP or service name.")
    print(f"- Check if port {crm_url.split(':')[-1].split('/')[0]} is exposed on the Pulse CRM server.")
    print("- Ensure the Pulse CRM (3EK-Pulse) is actually running.")

print("\n--- Diagnostic Complete ---")
