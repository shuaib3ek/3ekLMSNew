from app import create_app
from app.core.extensions import db
from app.training_management.models import ProgramParticipant
from app.core.shadow_models import ShadowStaffUser

app = create_app()
app.config['WTF_CSRF_ENABLED'] = True # enable CSRF to test!
app.config['TESTING'] = True

with app.test_client() as client:
    with app.app_context():
        user = ShadowStaffUser.query.filter_by(role='admin').first()
            
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        
    res = client.get('/training_management/61/')
    import re
    match = re.search(r'name=\"csrf_token\" value=\"([^\"]+)\"', res.data.decode('utf-8'))
    csrf = match.group(1) if match else ''
    
    res2 = client.post('/training_management/61/participants/add', data={
        'csrf_token': csrf,
        'name': 'Test Participant 2',
        'email': 'testparticipant2@example.com',
    }, follow_redirects=True)
    
    print('STATUS', res2.status_code)
    text = res2.data.decode('utf-8')
    if 'CSRF Error' in text:
        print('CSRF ERROR CAUGHT!')
        import sys
        sys.exit(1)
