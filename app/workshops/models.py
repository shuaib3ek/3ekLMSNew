"""
Workshops Module — LMS
Owns the full lifecycle: create → schedule → deliver → record → certify.

CRM cross-references (trainers, contacts, users, clients) are stored as plain
integer IDs (crm_*_id columns) with NO database-level FK constraints.
Entity details are resolved at runtime via app/crm_client/client.py.
"""
import json
from datetime import datetime
from app.core.extensions import db


class Workshop(db.Model):
    """
    Master record for a workshop / course event.
    Fully owned by the LMS — creation and management happen here.
    """
    __tablename__ = 'workshops'

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    subtitle = db.Column(db.String(255))
    category = db.Column(db.String(50), default='General')

    # Description & Content
    description = db.Column(db.Text)
    outcomes = db.Column(db.Text)        # JSON list: ["Learn X", "Master Y"]
    target_audience = db.Column(db.Text)
    agenda = db.Column(db.Text)

    # Schedule
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(20), default='09:00 AM IST')
    end_time = db.Column(db.String(20), default='05:00 PM IST')
    duration_display = db.Column(db.String(100))
    registration_deadline = db.Column(db.Date)
    timezone = db.Column(db.String(50), default='Asia/Kolkata')

    # Logistics
    mode = db.Column(db.String(20), default='online')   # online, in_person, hybrid
    venue = db.Column(db.String(255))
    meeting_link = db.Column(db.String(512))
    meeting_credentials = db.Column(db.String(512))

    # Capacity & Pricing
    total_seats = db.Column(db.Integer, default=30)
    fee_per_person = db.Column(db.Numeric(10, 2), default=0.00)
    currency = db.Column(db.String(10), default='INR')
    early_bird_fee = db.Column(db.Numeric(10, 2))
    early_bird_deadline = db.Column(db.Date)
    is_free = db.Column(db.Boolean, default=True)

    # Media
    banner_image_url = db.Column(db.String(512))
    brochure_url = db.Column(db.String(512))
    certificate_template = db.Column(db.String(512))
    certificates_enabled = db.Column(db.Boolean, default=False)

    # Status & Visibility
    status = db.Column(db.String(20), default='draft', index=True)
    is_public = db.Column(db.Boolean, default=False)
    featured = db.Column(db.Boolean, default=False)

    # ── CRM soft reference (NO FK constraint) ────────────────────────────────
    # Resolved via crm_client.get_user(crm_owner_id) when needed.
    crm_owner_id = db.Column(db.Integer, nullable=True)

    # ── CRM client reference (for B2B corporate workshops) ───────────────────
    # Resolved via crm_client.get_client(crm_client_id) when needed.
    crm_client_id = db.Column(db.Integer, nullable=True)

    internal_notes = db.Column(db.Text)

    # ── Enhancement Takeover Flags (Phase 3.0) ────────────────────────────────
    is_lms_managed = db.Column(db.Boolean, default=False)
    admin_ready = db.Column(db.Boolean, default=False)
    crm_engagement_id = db.Column(db.Integer, index=True, nullable=True) # Pulse trigger

    # Relationships (LMS-internal only)
    trainers = db.relationship('WorkshopTrainer', back_populates='workshop', cascade='all, delete-orphan')
    sessions = db.relationship('WorkshopSession', back_populates='workshop', cascade='all, delete-orphan',
                               order_by='WorkshopSession.session_date')
    registrations = db.relationship('WorkshopRegistration', back_populates='workshop', cascade='all, delete-orphan')
    email_logs = db.relationship('WorkshopEmailLog', back_populates='workshop', cascade='all, delete-orphan')
    documents = db.relationship('WorkshopDocument', back_populates='workshop', cascade='all, delete-orphan')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Workshop {self.title}>'

    @property
    def seats_booked(self):
        return sum(1 for r in self.registrations if r.status in ['confirmed', 'attended', 'pending'])

    @property
    def seats_available(self):
        return max(0, (self.total_seats or 0) - self.seats_booked)

    @property
    def is_full(self):
        return self.seats_available == 0

    @property
    def fill_percentage(self):
        if not self.total_seats:
            return 0
        return round((self.seats_booked / self.total_seats) * 100)

    @property
    def outcomes_list(self):
        if not self.outcomes:
            return []
        try:
            return json.loads(self.outcomes)
        except Exception:
            return [o.strip() for o in self.outcomes.split('\n') if o.strip()]

    @property
    def effective_fee(self):
        from datetime import date
        if self.early_bird_fee and self.early_bird_deadline and date.today() <= self.early_bird_deadline:
            return float(self.early_bird_fee)
        return float(self.fee_per_person or 0)

    @property
    def total_revenue(self):
        paid = [r for r in self.registrations if r.payment_status == 'paid']
        return sum(float(r.amount_paid or 0) for r in paid)

    @property
    def registration_url(self):
        try:
            from flask import current_app
            base = current_app.config.get('WEBSITE_BASE_URL', 'https://www.3ek.in')
        except RuntimeError:
            base = 'https://www.3ek.in'
        return f'{base}/workshops/{self.slug}'

    def sync_from_crm(self):
        """Updates local metadata from Pulse CRM live data."""
        if not self.crm_engagement_id:
            return False

        from app.crm_client import client as crm
        data = crm.get_program_detail(self.crm_engagement_id)
        if not data:
            return False

        # Update core metadata only if it's managed
        if self.is_lms_managed:
            self.title = data.get('topic', self.title)

        # Always sync Dates if crm_engagement_id exists
        start_str = data.get('start_date')
        end_str = data.get('end_date')

        from datetime import datetime
        if start_str:
            try:
                self.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except Exception:
                pass
        if end_str:
            try:
                self.end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except Exception:
                pass

        return True


class WorkshopTrainer(db.Model):
    """
    Maps one or more trainers to a workshop.
    crm_trainer_id is a soft reference to CRM's trainers table.
    Trainer profile resolved via crm_client.get_trainer(crm_trainer_id).
    """
    __tablename__ = 'workshop_trainers'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)

    # ── CRM soft reference (NO FK constraint) ────────────────────────────────
    crm_trainer_id = db.Column(db.Integer, nullable=False)

    role = db.Column(db.String(30), default='lead')   # lead, co_facilitator, guest
    confirmed = db.Column(db.Boolean, default=False)
    trainer_fee = db.Column(db.Numeric(10, 2))
    fee_currency = db.Column(db.String(10), default='INR')
    notes = db.Column(db.Text)

    workshop = db.relationship('Workshop', back_populates='trainers')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def trainer(self):
        """Transparently fetches trainer profile from CRM so old templates don't break."""
        from app.crm_client import client as crm
        t_data = crm.get_trainer(self.crm_trainer_id)
        
        class MockTrainer:
            def __init__(self, data):
                self.name = data.get('name') or f"{data.get('first_name','')} {data.get('last_name','')}".strip() or 'Expert Trainer'
                self.photo_url = data.get('profile_picture')
                self.bio = data.get('bio')
                self.years_experience = data.get('years_experience', 5)
                self.email = data.get('email')
                self.phone = data.get('phone')
        
        if t_data:
            return MockTrainer(t_data)
            
        return MockTrainer({})

    def __repr__(self):
        return f'<WorkshopTrainer workshop={self.workshop_id} crm_trainer={self.crm_trainer_id}>'


class WorkshopDocument(db.Model):
    """Materials, slides, and handouts for workshop participants."""
    __tablename__ = 'workshop_documents'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512), nullable=False)
    document_type = db.Column(db.String(50), default='Handout')
    size_bytes = db.Column(db.Integer)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ── CRM soft reference — who uploaded (NO FK constraint) ─────────────────
    crm_uploaded_by_id = db.Column(db.Integer, nullable=True)

    workshop = db.relationship('Workshop', back_populates='documents')

    def __repr__(self):
        return f'<WorkshopDocument {self.filename}>'


class WorkshopSession(db.Model):
    """Individual day/timeslot for a workshop. Also tracks MS Teams recordings."""
    __tablename__ = 'workshop_sessions'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)

    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    topic = db.Column(db.String(255))
    description = db.Column(db.Text)
    session_number = db.Column(db.Integer, default=1)

    # MS Teams
    teams_meeting_id = db.Column(db.String(255), unique=True, nullable=True)
    teams_join_url = db.Column(db.String(1000), nullable=True)

    # Recording pipeline
    recording_status = db.Column(db.String(20), default='pending')  # pending, encoding, ready, error
    graph_drive_id = db.Column(db.String(100))
    graph_item_id = db.Column(db.String(100))

    # AI Insights
    transcript_json = db.Column(db.JSON)
    ai_summary = db.Column(db.Text)
    ai_points = db.Column(db.JSON)
    ai_review_status = db.Column(db.String(20), default='draft')
    ai_chapters = db.Column(db.JSON)
    ai_pedagogical_audit = db.Column(db.JSON)

    # Webhook subscription
    graph_subscription_id = db.Column(db.String(255), nullable=True)
    graph_subscription_expires = db.Column(db.DateTime, nullable=True)

    workshop = db.relationship('Workshop', back_populates='sessions')

    def __repr__(self):
        return f'<WorkshopSession {self.session_date} — {self.topic}>'


class Learner(db.Model):
    """
    An individual learner who attends workshops.
    Managed entirely within the LMS database.
    """
    __tablename__ = 'learners'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))

    # ── Predefined Auth (Phase 3.0) ──────────────────────────────────────────
    username = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    company = db.Column(db.String(255))
    job_title = db.Column(db.String(255))

    # ── CRM soft reference for B2B company context (NO FK constraint) ──
    crm_client_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Learner {self.name} — {self.email}>'


class WorkshopRegistration(db.Model):
    __tablename__ = 'workshop_registrations'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)

    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'), nullable=False)
    learner = db.relationship('Learner', backref=db.backref('registrations', cascade='all, delete-orphan'))

    # Denormalized learner details (stored locally for quick access)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    company = db.Column(db.String(255))
    job_title = db.Column(db.String(255))

    # Status
    status = db.Column(db.String(20), default='pending')   # pending, confirmed, attended, cancelled

    # Payment
    payment_status = db.Column(db.String(20), default='free')   # free, pending, paid, refunded
    amount_paid = db.Column(db.Numeric(10, 2), default=0.00)
    payment_reference = db.Column(db.String(100))
    payment_method = db.Column(db.String(50))
    payment_date = db.Column(db.Date)

    # Source & Communication
    source = db.Column(db.String(30), default='website')   # website, invite, crm_assignment, manual
    confirmation_sent = db.Column(db.Boolean, default=False)
    confirmation_sent_at = db.Column(db.DateTime)
    confirmation_token = db.Column(db.String(100), unique=True)

    # Attendance & Feedback
    attended = db.Column(db.Boolean, default=False)
    feedback_submitted = db.Column(db.Boolean, default=False)
    feedback_score = db.Column(db.Integer)
    feedback_comment = db.Column(db.Text)

    notes = db.Column(db.Text)
    custom_answers = db.Column(db.Text)

    # Razorpay
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))

    # LMS Progress
    progress_data = db.Column(db.Text, default='{}')
    progress_percent = db.Column(db.Integer, default=0)

    # Analytics
    ip_address = db.Column(db.String(50))
    utm_source = db.Column(db.String(100))
    utm_campaign = db.Column(db.String(100))

    workshop = db.relationship('Workshop', back_populates='registrations')

    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_progress_data(self):
        try:
            return json.loads(self.progress_data or '{}')
        except Exception:
            return {}

    def __repr__(self):
        return f'<WorkshopRegistration {self.name} — {self.email}>'

    @property
    def status_badge(self):
        return {
            'pending': 'warning',
            'confirmed': 'success',
            'attended': 'info',
            'cancelled': 'danger',
        }.get(self.status, 'secondary')


class WorkshopEmailLog(db.Model):
    """Tracks every email blast sent for a workshop."""
    __tablename__ = 'workshop_email_logs'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)

    # ── CRM soft reference (NO FK constraint) ────────────────────────────────
    crm_sent_by_id = db.Column(db.Integer, nullable=True)

    email_type = db.Column(db.String(30), default='invitation')   # invitation, reminder, confirmation, post_event
    recipient_count = db.Column(db.Integer, default=0)
    subject = db.Column(db.String(255))
    filter_description = db.Column(db.String(255))
    notes = db.Column(db.Text)

    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    workshop = db.relationship('Workshop', back_populates='email_logs')

    def __repr__(self):
        return f'<WorkshopEmailLog workshop={self.workshop_id} type={self.email_type}>'


class GraphSubscription(db.Model):
    """Tracks active MS Graph webhook subscriptions for Teams recording detection."""
    __tablename__ = 'graph_subscriptions'

    id = db.Column(db.String(255), primary_key=True)   # Microsoft Subscription ID
    resource = db.Column(db.String(255), nullable=False)
    expiration_date = db.Column(db.DateTime, nullable=False)
    client_state_token = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='active')   # active, expired, renewing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OtpToken(db.Model):
    """
    Stores one-time passwords for Learner / Trainer / Client passwordless login.
    Stored in DB so they survive server restarts and are not session-dependent.
    """
    __tablename__ = 'otp_tokens'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    role = db.Column(db.String(30), nullable=False)   # learner, trainer, client
    code = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        return not self.used and datetime.utcnow() < self.expires_at

    def __repr__(self):
        return f'<OtpToken {self.email} ({self.role})>'



class SystemTask(db.Model):
    """
    Lightweight internal task queue for LMS background operations
    (Teams recording polling, webhook renewal, etc.).
    """
    __tablename__ = 'system_tasks'

    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(50), default='queued')   # queued, running, completed, failed
    retries = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=10)
    next_run_at = db.Column(db.DateTime, default=datetime.utcnow)

    error_log = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkshopVideoProgress(db.Model):
    """
    Tracks an individual learner's progress watching a session recording.
    """
    __tablename__ = 'workshop_video_progress'

    id = db.Column(db.Integer, primary_key=True)

    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'), nullable=False)

    session_id = db.Column(db.Integer, db.ForeignKey('workshop_sessions.id'), nullable=False)

    seconds_watched = db.Column(db.Integer, default=0)
    max_position = db.Column(db.Integer, default=0)
    last_position = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)

    first_watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_watched_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = db.relationship('WorkshopSession', backref='user_progress')

    __table_args__ = (
        db.UniqueConstraint('learner_id', 'session_id', name='uq_learner_session_progress'),
    )

    def __repr__(self):
        return f'<WorkshopVideoProgress learner={self.learner_id} session={self.session_id}>'


class Certificate(db.Model):
    """Issued certificates for completed workshops."""
    __tablename__ = 'certificates'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)
    registration_id = db.Column(db.Integer, db.ForeignKey('workshop_registrations.id'), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'), nullable=False)

    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    certificate_url = db.Column(db.String(512))
    certificate_number = db.Column(db.String(100), unique=True)

    workshop = db.relationship('Workshop')
    registration = db.relationship('WorkshopRegistration')

    def __repr__(self):
        return f'<Certificate {self.certificate_number}>'


class WorkshopActivityLog(db.Model):
    """
    Granular log of participant activity within a workshop.
    Tracks sessions, labs, and quest completions.
    """
    __tablename__ = 'workshop_activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'), nullable=False)
    registration_id = db.Column(db.Integer, db.ForeignKey('workshop_registrations.id'), nullable=False)
    
    activity_type = db.Column(db.String(50), nullable=False) # login, logout, lab_start, lab_end, quest_complete
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration_seconds = db.Column(db.Integer, default=0)
    metadata_json = db.Column(db.JSON) # Additional context

    workshop = db.relationship('Workshop')
    learner = db.relationship('Learner')
    registration = db.relationship('WorkshopRegistration')

    def __repr__(self):
        return f'<WorkshopActivityLog {self.learner_id} - {self.activity_type}>'
