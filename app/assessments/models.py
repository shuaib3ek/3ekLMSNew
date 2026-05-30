from datetime import datetime
from app.core.extensions import db


class ProgramAssessment(db.Model):
    """
    An assessment assigned to a program.
    Supports file uploads (PDF/link) and native MCQ quizzes.
    """
    __tablename__ = 'program_assessments'

    id = db.Column(db.Integer, primary_key=True)
    crm_engagement_id = db.Column(db.Integer, index=True, nullable=False)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    file_url = db.Column(db.String(512))            # PDF or external link
    assessment_type = db.Column(db.String(50), default='document')  # document | link | quiz

    # Scoring config (quiz mode)
    pass_score = db.Column(db.Integer, default=70)  # percentage required to pass
    time_limit_minutes = db.Column(db.Integer)      # None = unlimited
    max_attempts = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('Question', back_populates='assessment',
                                cascade='all, delete-orphan', order_by='Question.order')
    assignments = db.relationship('AssessmentAssignment', back_populates='assessment',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ProgramAssessment {self.title}>'


class Question(db.Model):
    """MCQ question belonging to a ProgramAssessment."""
    __tablename__ = 'assessment_questions'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('program_assessments.id'), nullable=False)

    text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(30), default='mcq')  # mcq | true_false | short_answer
    points = db.Column(db.Integer, default=1)
    order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessment = db.relationship('ProgramAssessment', back_populates='questions')
    options = db.relationship('QuestionOption', back_populates='question',
                              cascade='all, delete-orphan', order_by='QuestionOption.order')

    def __repr__(self):
        return f'<Question {self.id}: {self.text[:40]}>'


class QuestionOption(db.Model):
    """Answer option for an MCQ/True-False question."""
    __tablename__ = 'question_options'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)

    text = db.Column(db.String(512), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)

    question = db.relationship('Question', back_populates='options')

    def __repr__(self):
        return f'<QuestionOption {self.text[:30]} correct={self.is_correct}>'


class AssessmentAssignment(db.Model):
    """
    Links an assessment to a participant and tracks their result.
    """
    __tablename__ = 'assessment_assignments'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('program_assessments.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('program_participants.id'), nullable=False)

    status = db.Column(db.String(50), default='pending')   # pending | submitted | graded | passed | failed
    attempts = db.Column(db.Integer, default=0)

    # Grading
    score = db.Column(db.Float)              # percentage 0–100
    max_score = db.Column(db.Float)          # total possible points
    raw_points = db.Column(db.Float)         # points achieved
    graded_by = db.Column(db.String(100))    # 'auto' or admin name
    graded_at = db.Column(db.DateTime)
    feedback = db.Column(db.Text)            # admin or auto feedback message

    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessment = db.relationship('ProgramAssessment', back_populates='assignments')
    participant = db.relationship('ProgramParticipant',
                                  backref=db.backref('assessments', cascade='all, delete-orphan'))

    @property
    def passed(self):
        if self.score is None:
            return False
        return self.score >= (self.assessment.pass_score or 70)

    def __repr__(self):
        return f'<AssessmentAssignment Assessment:{self.assessment_id} Participant:{self.participant_id}>'


class QuizResponse(db.Model):
    """
    Stores a learner's answer to each question during a quiz attempt.
    One row per question per attempt.
    """
    __tablename__ = 'quiz_responses'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assessment_assignments.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('assessment_questions.id'), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    text_answer = db.Column(db.Text)   # for short_answer type
    is_correct = db.Column(db.Boolean)
    points_awarded = db.Column(db.Float, default=0)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignment = db.relationship('AssessmentAssignment', backref='responses')
    question = db.relationship('Question')
    selected_option = db.relationship('QuestionOption')

    def __repr__(self):
        return f'<QuizResponse assignment={self.assignment_id} question={self.question_id}>'
