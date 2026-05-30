import os
import uuid
from datetime import datetime
from flask import current_app, url_for
from celery import shared_task
from app.core.extensions import db

@shared_task(bind=True, max_retries=3)
def issue_certificate_task(self, assignment_id):
    """
    Background task to generate a PDF certificate and link it to a learner's account.
    """
    from app.assessments.models import AssessmentAssignment
    from app.workshops.models import Certificate, Learner
    from app.training_management.models import ProgramParticipant
    from app.services.certificate_service import generate_workshop_certificate

    assignment = AssessmentAssignment.query.get(assignment_id)
    if not assignment:
        return f"Assignment {assignment_id} not found."

    participant = ProgramParticipant.query.get(assignment.participant_id)
    if not participant or not participant.learner_id:
        return "No linked learner profile found."

    # Avoid duplicate certificates for the same program assessment
    existing = Certificate.query.filter_by(
        learner_id=participant.learner_id,
        assessment_assignment_id=assignment.id  # Assuming we add this field or keep it unique
    ).first()
    
    if existing:
        return f"Certificate already exists for assignment {assignment_id}."

    cert_number = f"3EK-CERT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    # Generate PDF
    try:
        learner = Learner.query.get(participant.learner_id)
        program_title = assignment.assessment.title
        
        pdf_buffer = generate_workshop_certificate(
            learner_name=learner.name,
            workshop_title=program_title,
            completion_date=datetime.utcnow()
        )
        
        upload_path = os.path.join(current_app.root_path, 'static', 'certificates')
        os.makedirs(upload_path, exist_ok=True)
        pdf_filename = f"{cert_number}.pdf"
        
        with open(os.path.join(upload_path, pdf_filename), 'wb') as f:
            f.write(pdf_buffer.read())
            
        cert_url = url_for('static', filename=f'certificates/{pdf_filename}')
        
        cert = Certificate(
            workshop_id=None,
            registration_id=None,
            assessment_assignment_id=assignment.id,
            learner_id=participant.learner_id,
            certificate_number=cert_number,
            certificate_url=cert_url,
            issued_at=datetime.utcnow(),
        )
        db.session.add(cert)
        db.session.commit()
        
        return f"Certificate {cert_number} issued successfully."
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Certificate generation failed: {str(e)}")
        # Retry logic
        raise self.retry(exc=e, countdown=60)
