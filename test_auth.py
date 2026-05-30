import os
import requests as http_requests

email = 'shuaib@3ek.in'
base = 'http://3ek-app:8000'
token = os.environ.get('CRM_SERVICE_TOKEN', '')
email_valid = False
user_data = {}

try:
    r = http_requests.get(f'{base}/api/v1/crm/contacts', headers={'X-Service-Token': token}, timeout=5)
    print("Status code:", r.status_code)
    if r.ok:
        contacts_list = r.json()
        if isinstance(contacts_list, dict) and 'data' in contacts_list:
            contacts_list = contacts_list['data']
        data = next((c for c in contacts_list if c.get('email', '').strip().lower() == email), None)
        print("Data found:", data)
        if data:
            email_valid = True
            user_data = {
                'id': data.get('id', 0),
                'email': email,
                'first_name': data.get('name', 'Client').split()[0],
                'last_name': '',
                'role': 'client',
                'crm_client_id': data.get('client_id'),
            }
            print("User data:", user_data)
except Exception as e:
    import traceback
    traceback.print_exc()

print("Email valid:", email_valid)
