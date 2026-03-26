from datetime import datetime
from app.core.extensions import db

class ProgramLab(db.Model):
    """
    A lab environment record for a program.
    """
    __tablename__ = 'program_labs'

    id = db.Column(db.Integer, primary_key=True)
    crm_engagement_id = db.Column(db.Integer, index=True, nullable=False)
    
    title = db.Column(db.String(255), nullable=False)
    lab_url = db.Column(db.String(512), nullable=False)
    
    access_start = db.Column(db.DateTime, nullable=True)
    access_end = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('LabAssignment', back_populates='lab', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ProgramLab {self.title}>'

class LabAssignment(db.Model):
    """
    Links a lab to a participant.
    """
    __tablename__ = 'lab_assignments'

    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey('program_labs.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('program_participants.id'), nullable=False)
    
    status = db.Column(db.String(50), default='pending') # pending, active, expired
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    lab = db.relationship('ProgramLab', back_populates='assignments')
    participant = db.relationship('ProgramParticipant', backref=db.backref('labs', cascade='all, delete-orphan'))

    @property
    def computed_status(self):
        now = datetime.utcnow()
        if self.lab.access_start and now < self.lab.access_start:
            return 'pending'
        if self.lab.access_end and now > self.lab.access_end:
            return 'expired'
        return 'active'

    def __repr__(self):
        return f'<LabAssignment Lab ID: {self.lab_id} Participant ID: {self.participant_id}>'
