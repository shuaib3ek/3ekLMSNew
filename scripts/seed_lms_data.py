import sys
import os

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.core.extensions import db
from app.training_management.models import ProgramParticipant, ProgramConfig
from app.assessments.models import ProgramAssessment, AssessmentAssignment
from app.labs.models import ProgramLab, LabAssignment

app = create_app()

def seed(crm_id):
    with app.app_context():
        # Check or Create Program Config
        config = ProgramConfig.query.filter_by(crm_engagement_id=crm_id).first()
        if not config:
            config = ProgramConfig(crm_engagement_id=crm_id)
            db.session.add(config)
        
        # ACTIVATE MODULE SYNC (forcefully)
        config.assessments_enabled = True
        config.labs_enabled = True
        
        # Add 10 Participants
        participants = []
        for i in range(1, 11):
            # Check if email exists
            email = f"participant{i}@example.com"
            existing = ProgramParticipant.query.filter_by(crm_engagement_id=crm_id, email=email).first()
            if not existing:
                p = ProgramParticipant(
                    crm_engagement_id=crm_id,
                    name=f"Sample Participant {i}",
                    email=email,
                    phone="1234567890",
                    organization="Sample Corp",
                    status="active"
                )
                db.session.add(p)
                participants.append(p)
            else:
                participants.append(existing)
            
        db.session.commit()
        
        # Add Assessment
        assessment = ProgramAssessment.query.filter_by(crm_engagement_id=crm_id).first()
        if not assessment:
            assessment = ProgramAssessment(
                crm_engagement_id=crm_id,
                title="Sample Pre-Training Assessment",
                file_url="https://example.com/assessment.pdf",
                assessment_type="link"
            )
            db.session.add(assessment)
            db.session.commit()
        
        # Add Lab
        lab = ProgramLab.query.filter_by(crm_engagement_id=crm_id).first()
        if not lab:
            lab = ProgramLab(
                crm_engagement_id=crm_id,
                title="Sample AWS Virtual Lab",
                lab_url="https://aws.amazon.com/console"
            )
            db.session.add(lab)
            db.session.commit()
        
        # Assign to participants
        for p in participants:
            # Check existing assignment
            aa = AssessmentAssignment.query.filter_by(assessment_id=assessment.id, participant_id=p.id).first()
            if not aa:
                aa = AssessmentAssignment(
                    assessment_id=assessment.id,
                    participant_id=p.id,
                    status="pending"
                )
                db.session.add(aa)
            
            la = LabAssignment.query.filter_by(lab_id=lab.id, participant_id=p.id).first()
            if not la:
                la = LabAssignment(
                    lab_id=lab.id,
                    participant_id=p.id,
                    status="active"
                )
                db.session.add(la)
            
        db.session.commit()
        print(f"Sample data seeded successfully for CRM ID {crm_id}! Modules forcefully activated.")

if __name__ == '__main__':
    crm_id = 61 # Default based on logs
    if len(sys.argv) > 1:
        crm_id = int(sys.argv[1])
    seed(crm_id)
