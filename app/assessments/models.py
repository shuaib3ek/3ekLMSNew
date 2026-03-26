from datetime import datetime
from app.core.extensions import db

class ProgramAssessment(db.Model):
    """
    An assessment assigned to a program.
    """
    __tablename__ = 'program_assessments'

    id = db.Column(db.Integer, primary_key=True)
    crm_engagement_id = db.Column(db.Integer, index=True, nullable=False)
    
    title = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512), nullable=False) # PDF or link
    assessment_type = db.Column(db.String(50), default='link') # pdf, link, questionnaire
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('AssessmentAssignment', back_populates='assessment', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ProgramAssessment {self.title}>'

class AssessmentAssignment(db.Model):
    """
    Links an assessment to a participant.
    """
    __tablename__ = 'assessment_assignments'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('program_assessments.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('program_participants.id'), nullable=False)
    
    status = db.Column(db.String(50), default='pending') # pending, submitted, graded
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessment = db.relationship('ProgramAssessment', back_populates='assignments')
    participant = db.relationship('ProgramParticipant', backref=db.backref('assessments', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<AssessmentAssignment Assessment ID: {self.assessment_id} Participant ID: {self.participant_id}>'
