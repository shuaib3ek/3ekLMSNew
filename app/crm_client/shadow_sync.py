from datetime import datetime
from app.core.extensions import db
from app.core.shadow_models import ShadowStaffUser, ShadowTrainer, ShadowClient, ShadowContact

def update_shadow_staff_user(user_data):
    if not user_data or 'id' not in user_data:
        return
    user = ShadowStaffUser.query.filter_by(crm_user_id=user_data['id']).first()
    if not user:
        user = ShadowStaffUser(crm_user_id=user_data['id'])
        db.session.add(user)
    
    user.email = user_data.get('email', user.email)
    user.first_name = user_data.get('first_name', user.first_name)
    user.last_name = user_data.get('last_name', user.last_name)
    user.role = user_data.get('role', user.role)
    # Note: password_hash is updated only during verify/login success
    user.last_synced = datetime.utcnow()
    db.session.commit()

def update_shadow_trainer(trainer_data):
    if not trainer_data or 'id' not in trainer_data:
        return
    trainer = ShadowTrainer.query.filter_by(crm_trainer_id=trainer_data['id']).first()
    if not trainer:
        trainer = ShadowTrainer(crm_trainer_id=trainer_data['id'])
        db.session.add(trainer)
    
    trainer.name = trainer_data.get('name', trainer.name)
    trainer.email = trainer_data.get('email', trainer.email)
    trainer.bio = trainer_data.get('bio', trainer.bio)
    trainer.photo_url = trainer_data.get('photo_url', trainer.photo_url)
    trainer.expertise = trainer_data.get('expertise', trainer.expertise)
    trainer.last_synced = datetime.utcnow()
    db.session.commit()

def update_shadow_client(client_data):
    if not client_data or 'id' not in client_data:
        return
    client = ShadowClient.query.filter_by(crm_client_id=client_data['id']).first()
    if not client:
        client = ShadowClient(crm_client_id=client_data['id'])
        db.session.add(client)
    
    client.name = client_data.get('name', client.name)
    client.domain = client_data.get('domain', client.domain)
    client.logo = client_data.get('logo', client.logo)
    client.last_synced = datetime.utcnow()
    db.session.commit()

def update_shadow_contact(contact_data, password=None):
    if not contact_data or 'id' not in contact_data:
        return
    contact = ShadowContact.query.filter_by(crm_contact_id=contact_data['id']).first()
    if not contact:
        contact = ShadowContact(crm_contact_id=contact_data['id'])
        db.session.add(contact)
    
    contact.name = contact_data.get('name', contact.name)
    contact.email = contact_data.get('email', contact.email)
    contact.crm_client_id = contact_data.get('client_id', contact.crm_client_id)
    
    if password:
        # We cache the hash when verify succeeds via CRM
        from werkzeug.security import generate_password_hash
        contact.password_hash = generate_password_hash(password)
        
    contact.last_synced = datetime.utcnow()
    db.session.commit()
