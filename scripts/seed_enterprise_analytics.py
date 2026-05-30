import sys
import os
import random
from datetime import datetime, date, timedelta

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.organizations.models import Organization
from app.workshops.models import Workshop, WorkshopSession, Learner, WorkshopRegistration
from app.training_management.models import ProgramParticipant, ProgramConfig
from app.assessments.models import ProgramAssessment, Question, QuestionOption, AssessmentAssignment
from app.labs.models import ProgramLab, LabAssignment
from app.crm_client.client import fetch_pulse_programs, get_client

ORG_DATA = [
    ("Hexaware Technologies", "hexaware", "#119DAB"),
    ("Infosys Limited", "infosys", "#0284c7"),
    ("Wipro Enterprises", "wipro", "#059669"),
    ("Tata Consultancy Services", "tcs", "#7c3aed"),
    ("Accenture Strategy & Tech", "accenture", "#dc2626")
]

SAMPLE_QUESTIONS = [
    ("What is the primary benefit of a Kubernetes Service Mesh like Istio?", ["Traffic management & mTLS", "Database indexing", "Hardware virtualization", "CSS styling"], 0),
    ("Which AWS service provides highly available Layer 4 load balancing?", ["Network Load Balancer (NLB)", "Amazon S3", "AWS Lambda", "Amazon RDS"], 0),
    ("What does 'Zero-Copy' cloning in Snowflake achieve?", ["Metadata duplication without storage replication", "Full physical table duplication", "Deleting backup archives", "Encrypting passwords"], 0),
    ("In PyTorch, what is the purpose of optimizer.zero_grad()?", ["Clearing accumulated gradients before backprop", "Increasing learning rate", "Saving model weights to disk", "Importing datasets"], 0),
    ("Which HTTP method is idempotent and used for full resource replacement?", ["PUT", "POST", "PATCH", "OPTIONS"], 0)
]

LAB_TITLES = [
    "AWS Multi-Region Enterprise VPC & Transit Gateway Sandbox",
    "Kubernetes Multi-Cluster GitOps & Istio Mesh Environment",
    "Databricks & PyTorch Multi-GPU Fine-Tuning Cluster",
    "Snowflake Secure Data Sharing & Masking Policy Vault",
    "Terraform Enterprise Cloud Infrastructure Automation Lab",
    "Prometheus & Grafana Distributed Tracing Sandbox",
    "Azure DevOps CI/CD Secure Release Pipeline Lab",
    "Kafka Distributed Event Streaming & ksqlDB VM",
    "FastAPI & PostgreSQL pgvector Semantic Search Instance",
    "Rust High-Performance Asynchronous Proxy Sandbox"
]

def seed_lms_analytics():
    app = create_app()
    with app.app_context():
        print("[LMS Seed] Starting enterprise training simulation engine in 3ek-lms...")

        # 1. Ensure Organizations exist
        org_map = {}
        for name, slug, color in ORG_DATA:
            org = Organization.query.filter_by(slug=slug).first()
            if not org:
                org = Organization(name=name, slug=slug, primary_color=color, is_active=True)
                db.session.add(org)
                db.session.commit()
            org_map[org.name] = org
        print(f"[LMS Seed] Verified {len(org_map)} Organizations.")

        # 2. Fetch CRM Programs
        programs = fetch_pulse_programs()
        if not programs:
            print("[LMS Seed] WARNING: No CRM programs fetched from Pulse! Run CRM seed script first.")
            return

        print(f"[LMS Seed] Fetched {len(programs)} live CRM programs from Pulse API.")

        # 3. Process up to 25 Engagements
        total_participants = 0
        total_assessments = 0
        total_labs = 0
        total_workshops = 0

        for idx, prog in enumerate(programs[:25]):
            prog_id = prog.get('id')
            topic = prog.get('topic', f'Enterprise Engagement #{prog_id}')
            # Resolve organization
            client_id = prog.get('client_id')
            client_name = prog.get('client_name')


            
            if client_name:
                org = org_map.get(client_name)
            else:
                client_data = get_client(client_id) if client_id else None
                client_name = client_data.get('name') if client_data else random.choice(list(org_map.keys()))
                org = org_map.get(client_name)
                
            if not org:
                org = Organization.query.get(1)


            # Ensure ProgramConfig
            cfg = ProgramConfig.query.filter_by(crm_engagement_id=prog_id).first()
            if not cfg:
                cfg = ProgramConfig(
                    crm_engagement_id=prog_id,
                    assessments_enabled=True,
                    labs_enabled=True
                )
                db.session.add(cfg)
                db.session.commit()

            # Create 30 Participants
            current_parts = ProgramParticipant.query.filter_by(crm_engagement_id=prog_id).all()
            if len(current_parts) < 30:
                needed = 30 - len(current_parts)
                parts_to_add = []
                for p_num in range(needed):
                    idx_global = len(current_parts) + p_num + 1
                    email = f"eng{prog_id}.user{idx_global}@{org.slug}.com"
                    
                    # Ensure Learner account exists
                    learner = Learner.query.filter_by(email=email).first()
                    if not learner:
                        learner = Learner(
                            organization_id=org.id,
                            name=f"{client_name.split()[0]} Engineer {idx_global}",
                            email=email,
                            company=client_name,
                            job_title="Senior Software Engineer",
                            crm_client_id=client_id
                        )
                        db.session.add(learner)
                        db.session.flush()

                    part = ProgramParticipant(
                        crm_engagement_id=prog_id,
                        name=learner.name,
                        email=learner.email,
                        organization=client_name,
                        status=random.choice(["active", "completed", "invited"]),
                        learner_id=learner.id
                    )
                    parts_to_add.append(part)
                
                db.session.add_all(parts_to_add)
                db.session.commit()
                current_parts.extend(parts_to_add)
            
            total_participants += len(current_parts)

            # For the first 10 engagements, create a full LMS Workshop
            if idx < 10:
                slug_w = f"workshop-eng-{prog_id}-{org.slug}"
                workshop = Workshop.query.filter_by(slug=slug_w).first()
                if not workshop:
                    start_str = prog.get('start_date')
                    end_str = prog.get('end_date')
                    try:
                        s_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else date.today()
                        e_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else s_date + timedelta(days=4)
                    except Exception:
                        s_date = date.today()
                        e_date = s_date + timedelta(days=4)

                    workshop = Workshop(
                        organization_id=org.id,
                        title=f"[Masterclass] {topic}",
                        slug=slug_w,
                        subtitle=f"Enterprise Enablement for {client_name}",
                        category="Enterprise Training",
                        description="Comprehensive hands-on deep dive covering advanced architecture and best practices.",
                        start_date=s_date,
                        end_date=e_date,
                        total_seats=30,
                        fee_per_person=25000.00,
                        is_free=False,
                        status="published",
                        is_public=True,
                        is_lms_managed=True,
                        crm_engagement_id=prog_id
                    )
                    db.session.add(workshop)
                    db.session.commit()

                    # Add Workshop Registrations for the participants
                    for part in current_parts:
                        reg = WorkshopRegistration.query.filter_by(workshop_id=workshop.id, learner_id=part.learner_id).first()
                        if not reg:
                            reg = WorkshopRegistration(
                                organization_id=org.id,
                                workshop_id=workshop.id,
                                learner_id=part.learner_id,
                                name=part.name,
                                email=part.email,
                                company=part.organization,
                                status=random.choice(["confirmed", "attended"]),
                                payment_status="paid",
                                amount_paid=25000.00
                            )
                            db.session.add(reg)
                    db.session.commit()
                total_workshops += 1

            # Create 1 Assessment per Engagement
            ass = ProgramAssessment.query.filter_by(crm_engagement_id=prog_id).first()
            if not ass:
                ass = ProgramAssessment(
                    crm_engagement_id=prog_id,
                    title=f"Final Certification Assessment: {topic[:50]}",
                    description="Comprehensive validation covering core architecture, implementation, and edge cases.",
                    assessment_type="quiz",
                    pass_score=70
                )
                db.session.add(ass)
                db.session.commit()

                # Add Questions
                for q_idx, (q_text, opts, corr_idx) in enumerate(SAMPLE_QUESTIONS):
                    q = Question(
                        assessment_id=ass.id,
                        text=q_text,
                        question_type="mcq",
                        points=10,
                        order=q_idx
                    )
                    db.session.add(q)
                    db.session.flush()

                    for opt_idx, opt_text in enumerate(opts):
                        o = QuestionOption(
                            question_id=q.id,
                            text=opt_text,
                            is_correct=(opt_idx == corr_idx),
                            order=opt_idx
                        )
                        db.session.add(o)
                db.session.commit()

            # Ensure all participants have AssessmentAssignment with realistic scores
            for part in current_parts:
                assign = AssessmentAssignment.query.filter_by(assessment_id=ass.id, participant_id=part.id).first()
                if not assign:
                    score = random.choice([70.0, 80.0, 90.0, 100.0, 60.0]) # Most pass
                    assign = AssessmentAssignment(
                        assessment_id=ass.id,
                        participant_id=part.id,
                        status="passed" if score >= 70 else "failed",
                        attempts=1,
                        score=score,
                        max_score=50.0,
                        raw_points=(score / 100.0) * 50.0,
                        graded_by="auto",
                        graded_at=datetime.utcnow()
                    )
                    db.session.add(assign)
            db.session.commit()
            total_assessments += 1

            # For the first 10 engagements, also create Cloud Labs
            if idx < 10:
                lab_title = LAB_TITLES[idx % len(LAB_TITLES)]
                lab = ProgramLab.query.filter_by(crm_engagement_id=prog_id, title=lab_title).first()
                if not lab:
                    lab = ProgramLab(
                        crm_engagement_id=prog_id,
                        title=lab_title,
                        lab_url=f"https://labs.3ek.cloud/env/{prog_id}/sandbox-{idx}",
                        access_start=datetime.utcnow() - timedelta(days=2),
                        access_end=datetime.utcnow() + timedelta(days=10)
                    )
                    db.session.add(lab)
                    db.session.commit()

                # Assign lab to participants
                for part in current_parts:
                    lab_assign = LabAssignment.query.filter_by(lab_id=lab.id, participant_id=part.id).first()
                    if not lab_assign:
                        lab_assign = LabAssignment(
                            lab_id=lab.id,
                            participant_id=part.id,
                            status=random.choice(["active", "completed", "active"])
                        )
                        db.session.add(lab_assign)
                db.session.commit()
                total_labs += 1

        print(f"[LMS Seed] Complete! Successfully seeded:")
        print(f"  - 25 Program Configs & Assessments ({total_assessments} total)")
        print(f"  - {total_workshops} Dedicated LMS Workshops")
        print(f"  - {total_participants} Total Participants / Learners")
        print(f"  - {total_labs} Cloud VM Sandboxes assigned")

if __name__ == "__main__":
    seed_lms_analytics()
