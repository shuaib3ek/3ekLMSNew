from datetime import datetime
from app.core.extensions import db

class ShadowStaffUser(db.Model):
    """Local cache of CRM Staff Users."""
    __tablename__ = 'shadow_staff_users'

    id = db.Column(db.Integer, primary_key=True)
    crm_user_id = db.Column(db.Integer, unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    role = db.Column(db.String(50), default='staff')
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ShadowStaffUser {self.email}>'

class ShadowTrainer(db.Model):
    """Local cache of CRM Trainers."""
    __tablename__ = 'shadow_trainers'

    id = db.Column(db.Integer, primary_key=True)
    crm_trainer_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    expertise = db.Column(db.Text) # Stored as comma-separated or JSON
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ShadowTrainer {self.name}>'

class ShadowClient(db.Model):
    """Local cache of CRM Clients (Companies)."""
    __tablename__ = 'shadow_clients'

    id = db.Column(db.Integer, primary_key=True)
    crm_client_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255))
    logo = db.Column(db.String(500))
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ShadowClient {self.name}>'

class ShadowContact(db.Model):
    """Local cache of CRM Contacts (Client Users)."""
    __tablename__ = 'shadow_contacts'

    id = db.Column(db.Integer, primary_key=True)
    crm_contact_id = db.Column(db.Integer, unique=True, nullable=False)
    crm_client_id = db.Column(db.Integer, nullable=True) # Soft reference to ShadowClient's crm_client_id
    
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255))
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ShadowContact {self.email}>'
