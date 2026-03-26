from app import create_app
from app.core.extensions import db
from app.training_management.models import ProgramParticipant
from app.core.shadow_models import ShadowStaffUser

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.test_client() as client:
    with app.app_context():
        user = ShadowStaffUser.query.filter_by(role='admin').first()
        if not user:
            print("No admin user found.")
            exit(1)
            
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        
    res = client.post('/training_management/61/participants/add', data={
        'name': 'Test Participant',
        'email': 'testparticipant@example.com',
        'phone': '1234567890',
        'organization': 'Acme Corp'
    }, follow_redirects=True)
    
    print('STATUS', res.status_code)
    text = res.data.decode('utf-8')
    if 'Test Participant' in text:
        print('SUCCESS: Participant name found in HTML.')
    if 'Participant added successfully' in text:
        print('SUCCESS: Flash message found in HTML.')
    
    with app.app_context():
        print('DB PARTICIPANTS:', ProgramParticipant.query.count())
