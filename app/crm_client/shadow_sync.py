from datetime import datetime
from flask import current_app
from app.core.extensions import db
from app.core.shadow_models import ShadowStaffUser, ShadowTrainer, ShadowClient, ShadowContact

def update_shadow_staff_user(user_data):
    if not user_data or 'id' not in user_data:
        return
    try:
        user = ShadowStaffUser.query.filter_by(crm_user_id=user_data['id']).first()
        if not user:
            user = ShadowStaffUser(crm_user_id=user_data['id'])
            db.session.add(user)
        
        user.email = user_data.get('email', user.email)
        user.first_name = user_data.get('first_name', user.first_name)
        user.last_name = user_data.get('last_name', user.last_name)
        user.role = user_data.get('role', user.role)
        user.last_synced = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[LMS] Shadow sync error for staff {user_data.get('email')}: {e}")

def update_shadow_trainer(trainer_data):
    if not trainer_data or 'id' not in trainer_data:
        return
    try:
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
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[LMS] Shadow sync error for trainer {trainer_data.get('name')}: {e}")

def update_shadow_client(client_data):
    if not client_data or 'id' not in client_data:
        return
    try:
        client = ShadowClient.query.filter_by(crm_client_id=client_data['id']).first()
        if not client:
            client = ShadowClient(crm_client_id=client_data['id'])
            db.session.add(client)
        
        client.name = client_data.get('name', client.name)
        client.domain = client_data.get('domain', client.domain)
        client.logo = client_data.get('logo', client.logo)
        
        # Dynamic organization resolution
        from app.organizations.models import Organization
        resolved_org = None
        if client.name:
            name_lower = client.name.lower()
            if 'hexaware' in name_lower or 'hexa' in name_lower:
                resolved_org = Organization.query.filter_by(slug='hex').first()
            elif 'infosys' in name_lower or 'infy' in name_lower:
                resolved_org = Organization.query.filter_by(slug='infosys').first()
            elif 'wipro' in name_lower:
                resolved_org = Organization.query.filter_by(slug='wipro').first()
            elif 'tcs' in name_lower or 'tata consultancy' in name_lower or 'tata advanced' in name_lower:
                resolved_org = Organization.query.filter_by(slug='tcs').first()
            elif 'accenture' in name_lower:
                resolved_org = Organization.query.filter_by(slug='accenture').first()
        
        if not resolved_org and client.domain:
            domain_lower = client.domain.lower()
            resolved_org = Organization.query.filter(Organization.permitted_domains.ilike(f"%{domain_lower}%")).first()
            
        if resolved_org:
            client.organization_id = resolved_org.id
            
        client.last_synced = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[LMS] Shadow sync error for client {client_data.get('name')}: {e}")

def update_shadow_contact(contact_data, password=None):
    if not contact_data or 'id' not in contact_data:
        return
    try:
        contact = ShadowContact.query.filter_by(crm_contact_id=contact_data['id']).first()
        if not contact:
            contact = ShadowContact(crm_contact_id=contact_data['id'])
            db.session.add(contact)
        
        contact.name = contact_data.get('name', contact.name)
        contact.email = contact_data.get('email', contact.email)
        contact.crm_client_id = contact_data.get('client_id', contact.crm_client_id)
        
        # Dynamic organization resolution
        from app.organizations.models import Organization
        resolved_org = None
        if contact.email:
            email_lower = contact.email.lower()
            if 'hexaware.com' in email_lower or 'hexa.com' in email_lower:
                resolved_org = Organization.query.filter_by(slug='hex').first()
            elif 'infosys.com' in email_lower or 'infy.com' in email_lower:
                resolved_org = Organization.query.filter_by(slug='infosys').first()
            elif 'wipro.com' in email_lower:
                resolved_org = Organization.query.filter_by(slug='wipro').first()
            elif 'tcs.com' in email_lower:
                resolved_org = Organization.query.filter_by(slug='tcs').first()
            elif 'accenture.com' in email_lower:
                resolved_org = Organization.query.filter_by(slug='accenture').first()
                
            if not resolved_org and '@' in email_lower:
                domain = email_lower.split('@')[1]
                resolved_org = Organization.query.filter(Organization.permitted_domains.ilike(f"%{domain}%")).first()
                
        if not resolved_org and contact.crm_client_id:
            c = ShadowClient.query.filter_by(crm_client_id=contact.crm_client_id).first()
            if c:
                contact.organization_id = c.organization_id
        elif resolved_org:
            contact.organization_id = resolved_org.id
            
        if password:
            from werkzeug.security import generate_password_hash
            contact.password_hash = generate_password_hash(password)
            
        contact.last_synced = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[LMS] Shadow sync error for contact {contact_data.get('email') or contact_data.get('name')}: {e}")
