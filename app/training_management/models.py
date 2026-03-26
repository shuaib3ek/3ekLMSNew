from datetime import datetime
from app.core.extensions import db

class ProgramParticipant(db.Model):
    """
    Participants enrolled in a specific CRM program.
    """
    __tablename__ = 'program_participants'

    id = db.Column(db.Integer, primary_key=True)
    crm_engagement_id = db.Column(db.Integer, index=True, nullable=False)
    
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    organization = db.Column(db.String(255))
    
    status = db.Column(db.String(50), default='invited') # invited, active, completed
    source = db.Column(db.String(50), default='manual')  # manual, excel_upload
    
    # ── Phase 2: Link to Learner Account ──
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'), nullable=True)
    learner = db.relationship('Learner', backref=db.backref('program_assignments', lazy='dynamic'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Note: These backrefs will be defined in the respective models
    # assessments = db.relationship('AssessmentAssignment', back_populates='participant', cascade='all, delete-orphan')
    # labs = db.relationship('LabAssignment', back_populates='participant', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ProgramParticipant {self.email}>'

class ProgramConfig(db.Model):
    """
    LMS-side configuration overrides for a CRM program.
    """
    __tablename__ = 'program_configs'

    id = db.Column(db.Integer, primary_key=True)
    crm_engagement_id = db.Column(db.Integer, unique=True, index=True, nullable=False)
    
    assessments_enabled = db.Column(db.Boolean, default=False)
    labs_enabled = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProgramConfig CRM ID: {self.crm_engagement_id}>'
