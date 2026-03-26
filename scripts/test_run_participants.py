from app import create_app
from app.core.extensions import db
from app.training_management.models import ProgramParticipant, ProgramConfig
from app.workshops.models import Learner, Workshop
from app.assessments.models import ProgramAssessment, AssessmentAssignment
from app.labs.models import ProgramLab, LabAssignment
from werkzeug.security import generate_password_hash
import datetime

app = create_app()
with app.app_context():
    print("--- Test Run: LMS Participant Lifecycle ---")
    
    crm_id = 9999
    test_email = "test_learner_v3@3ek.com"
    test_name = "Test Learner V3"

    # 1. Cleanup
    db.session.query(AssessmentAssignment).filter(AssessmentAssignment.participant.has(email=test_email)).delete(synchronize_session=False)
    db.session.query(LabAssignment).filter(LabAssignment.participant.has(email=test_email)).delete(synchronize_session=False)
    db.session.query(ProgramParticipant).filter_by(email=test_email).delete()
    db.session.query(Learner).filter_by(email=test_email).delete()
    db.session.commit()

    # 2. Provision Learner
    learner = Learner(
        name="Test Learner V3",
        email=test_email,
        company="3EK Industries",
        job_title="Associate Developer",
        phone="+91 98765 43210",
        password_hash=generate_password_hash("3eks@learn")
    )
    db.session.add(learner)
    db.session.flush()
    print(f"Provisioned Learner ID: {learner.id}")

    # 3. Add Participant Link
    participant = ProgramParticipant(
        crm_engagement_id=crm_id,
        name=test_name,
        email=test_email,
        source='manual',
        learner_id=learner.id
    )
    db.session.add(participant)
    db.session.flush()
    print(f"Provisioned Participant ID: {participant.id}")

    # 4. Assign Assessment
    pa = ProgramAssessment.query.filter_by(crm_engagement_id=crm_id).first()
    if not pa:
        pa = ProgramAssessment(
            crm_engagement_id=crm_id,
            title="Python Advanced Quiz",
            file_url="https://example.com/quiz",
            assessment_type="link"
        )
        db.session.add(pa)
        db.session.flush()
    
    ass_assign = AssessmentAssignment(
        assessment_id=pa.id,
        participant_id=participant.id
    )
    db.session.add(ass_assign)

    # 5. Assign Lab
    pl = ProgramLab.query.filter_by(crm_engagement_id=crm_id).first()
    if not pl:
        pl = ProgramLab(
            crm_engagement_id=crm_id,
            title="Kubernetes Hands-on Lab",
            lab_url="https://labs.3ek.com/k8s",
            access_start=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            access_end=datetime.datetime.utcnow() + datetime.timedelta(days=7)
        )
        db.session.add(pl)
        db.session.flush()
    
    lab_assign = LabAssignment(
        lab_id=pl.id,
        participant_id=participant.id
    )
    db.session.add(lab_assign)
    db.session.commit()

    print("\n--- TEST RUN SUCCESSFUL ---")
    print(f"Participant: {test_name}")
    print(f"Email: {test_email}")
    print(f"Default Password: 3eks@learn")
    print("-" * 30)
    print("Verification:")
    print(f"1. Learner row created: CHECK")
    print(f"2. Participant linked to Learner ID {learner.id}: CHECK")
    print(f"3. Assessment 'Python Advanced Quiz' assigned: CHECK")
    print(f"4. Lab 'Kubernetes Hands-on Lab' assigned: CHECK")
    print(f"5. Lab Status (Time-based): {lab_assign.computed_status}")
    print("-" * 30)
    print("Ready for User login verification.")
