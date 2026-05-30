from datetime import datetime
from app.core.extensions import db

class Organization(db.Model):
    """
    Master record for a tenant (Organization) in the LMS.
    Every core entity (Workshops, Learners, etc.) will belong to an organization.
    """
    __tablename__ = 'organizations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    
    # Branding & Customisation (Dormant for now)
    primary_color = db.Column(db.String(7), default='#0ea5e9') # Midnight Sky default
    logo_url = db.Column(db.String(512))
    custom_domain = db.Column(db.String(255), unique=True)
    
    # Configuration
    is_active = db.Column(db.Boolean, default=True)
    allow_self_registration = db.Column(db.Boolean, default=False)
    permitted_domains = db.Column(db.Text) # Comma separated list like 'hexaware.com, hex.in'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Organization {self.name}>'
