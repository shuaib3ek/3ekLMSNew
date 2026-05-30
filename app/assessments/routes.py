import os
import uuid
from datetime import datetime
from flask import render_template, request, flash, redirect, url_for, current_app, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import assessments_bp
from app.core.extensions import db
from app.training_management.models import ProgramConfig, ProgramParticipant
from app.assessments.models import (
    ProgramAssessment, AssessmentAssignment,
    Question, QuestionOption, QuizResponse
)
from app.crm_client.client import fetch_pulse_program_detail


# ─── Admin: List Programs ───────────────────────────────────────────────────────

@assessments_bp.route('/')
@login_required
def list_assessments():
    """List all programs that have assessments enabled."""
    configs = ProgramConfig.query.filter_by(assessments_enabled=True).all()
    enabled_ids = [c.crm_engagement_id for c in configs]

    from app.crm_client.client import fetch_pulse_programs
    all_programs = fetch_pulse_programs()
    programs = [p for p in all_programs if p.get('id') in enabled_ids]

    # Attach stats per program
    for p in programs:
        eid = p['id']
        p['assessment_count'] = ProgramAssessment.query.filter_by(crm_engagement_id=eid).count()
        p['participant_count'] = ProgramParticipant.query.filter_by(crm_engagement_id=eid).count()
        total = AssessmentAssignment.query.join(ProgramAssessment).filter(
            ProgramAssessment.crm_engagement_id == eid).count()
        passed = AssessmentAssignment.query.join(ProgramAssessment).filter(
            ProgramAssessment.crm_engagement_id == eid,
            AssessmentAssignment.status == 'passed').count()
        p['completion_rate'] = round((passed / total * 100) if total else 0)

    return render_template('assessments/list.html', programs=programs)


# ─── Admin: Program Assessment Detail ──────────────────────────────────────────

@assessments_bp.route('/<int:crm_engagement_id>/')
@login_required
def detail(crm_engagement_id):
    """View and manage assessments for a specific program."""
    config = ProgramConfig.query.filter_by(
        crm_engagement_id=crm_engagement_id, assessments_enabled=True).first()
    if not config:
        flash("Assessments are not enabled for this program.", "warning")
        return redirect(url_for('assessments.list_assessments'))

    program = fetch_pulse_program_detail(crm_engagement_id)
    if not program:
        abort(404)

    assessments = ProgramAssessment.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    participants = ProgramParticipant.query.filter_by(crm_engagement_id=crm_engagement_id).all()
    assignments = (AssessmentAssignment.query
                   .join(ProgramAssessment)
                   .filter(ProgramAssessment.crm_engagement_id == crm_engagement_id)
                   .all())

    return render_template(
        'assessments/detail.html',
        program=program,
        assessments=assessments,
        participants=participants,
        assignments=assignments
    )


# ─── Admin: Upload Assessment (file / link) ─────────────────────────────────────

@assessments_bp.route('/<int:crm_engagement_id>/upload', methods=['POST'])
@login_required
def upload_assessment(crm_engagement_id):
    title = request.form.get('title')
    a_type = request.form.get('type', 'document')
    pass_score = int(request.form.get('pass_score', 70))
    time_limit = request.form.get('time_limit_minutes') or None
    max_attempts = int(request.form.get('max_attempts', 1))
    description = request.form.get('description', '')

    file_url = None

    if a_type == 'link':
        file_url = request.form.get('external_url', '')
    elif a_type in ('document', 'quiz'):
        file = request.files.get('file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'assessments')
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))
            file_url = url_for('static', filename=f'uploads/assessments/{filename}')

    assessment = ProgramAssessment(
        crm_engagement_id=crm_engagement_id,
        title=title,
        description=description,
        file_url=file_url,
        assessment_type=a_type,
        pass_score=pass_score,
        time_limit_minutes=int(time_limit) if time_limit else None,
        max_attempts=max_attempts
    )
    db.session.add(assessment)
    db.session.commit()
    flash('Assessment created successfully.', 'success')
    return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))


# ─── Admin: Quiz Builder — Add Question ────────────────────────────────────────

@assessments_bp.route('/quiz/<int:assessment_id>/add-question', methods=['POST'])
@login_required
def add_question(assessment_id):
    assessment = ProgramAssessment.query.get_or_404(assessment_id)
    text = request.form.get('text', '').strip()
    q_type = request.form.get('question_type', 'mcq')
    points = int(request.form.get('points', 1))

    if not text:
        flash('Question text is required.', 'error')
        return redirect(url_for('assessments.quiz_builder', assessment_id=assessment_id))

    order = len(assessment.questions)
    question = Question(
        assessment_id=assessment_id,
        text=text,
        question_type=q_type,
        points=points,
        order=order
    )
    db.session.add(question)
    db.session.flush()  # get question.id

    # Add options
    options = request.form.getlist('options[]')
    correct_index = int(request.form.get('correct_option', 0))
    for i, opt_text in enumerate(options):
        if opt_text.strip():
            db.session.add(QuestionOption(
                question_id=question.id,
                text=opt_text.strip(),
                is_correct=(i == correct_index),
                order=i
            ))

    db.session.commit()
    flash('Question added.', 'success')
    return redirect(url_for('assessments.quiz_builder', assessment_id=assessment_id))


# ─── Admin: Quiz Builder — Delete Question ─────────────────────────────────────

@assessments_bp.route('/question/<int:question_id>/delete', methods=['POST'])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    assessment_id = question.assessment_id
    db.session.delete(question)
    db.session.commit()
    flash('Question removed.', 'success')
    return redirect(url_for('assessments.quiz_builder', assessment_id=assessment_id))


# ─── Admin: Quiz Builder Page ───────────────────────────────────────────────────

@assessments_bp.route('/quiz/<int:assessment_id>/builder')
@login_required
def quiz_builder(assessment_id):
    assessment = ProgramAssessment.query.get_or_404(assessment_id)
    return render_template('assessments/quiz_builder.html', assessment=assessment)


# ─── Admin: Assign Assessment to Participants ──────────────────────────────────

@assessments_bp.route('/<int:crm_engagement_id>/assign', methods=['POST'])
@login_required
def assign_assessment(crm_engagement_id):
    assessment_id = request.form.get('assessment_id')
    participant_ids = request.form.getlist('participant_ids')

    if not assessment_id or not participant_ids:
        flash('Please select an assessment and at least one participant.', 'error')
        return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))

    count = 0
    for pid in participant_ids:
        existing = AssessmentAssignment.query.filter_by(
            assessment_id=assessment_id, participant_id=pid).first()
        if not existing:
            db.session.add(AssessmentAssignment(
                assessment_id=assessment_id,
                participant_id=pid
            ))
            count += 1

    db.session.commit()
    flash(f'Assessment assigned to {count} participant(s).', 'success')
    return redirect(url_for('assessments.detail', crm_engagement_id=crm_engagement_id))


# ─── Admin: Grade a Submission ─────────────────────────────────────────────────

@assessments_bp.route('/assignment/<int:assignment_id>/grade', methods=['POST'])
@login_required
def grade_assignment(assignment_id):
    assignment = AssessmentAssignment.query.get_or_404(assignment_id)
    score = float(request.form.get('score', 0))
    feedback = request.form.get('feedback', '')

    assignment.score = score
    assignment.feedback = feedback
    assignment.graded_by = current_user.username or 'admin'
    assignment.graded_at = datetime.utcnow()
    assignment.status = 'passed' if assignment.passed else 'failed'

    db.session.commit()

    # Auto-issue certificate if passed
    if assignment.status == 'passed':
        _auto_issue_certificate(assignment)

    flash(f'Assignment graded: {score:.1f}% — {"PASSED ✓" if assignment.status == "passed" else "FAILED ✗"}', 'success')
    crm_id = assignment.assessment.crm_engagement_id
    return redirect(url_for('assessments.detail', crm_engagement_id=crm_id))


# ─── Learner: Take Quiz ─────────────────────────────────────────────────────────

@assessments_bp.route('/take/<int:assignment_id>')
@login_required
def take_quiz(assignment_id):
    """Learner-facing quiz taking page."""
    from app.training_management.models import ProgramParticipant
    assignment = AssessmentAssignment.query.get_or_404(assignment_id)
    participant = ProgramParticipant.query.get_or_404(assignment.participant_id)

    # Security: ensure this learner owns this assignment
    if participant.learner_id != current_user.id:
        abort(403)

    assessment = assignment.assessment
    if assignment.attempts >= (assessment.max_attempts or 1):
        flash('You have used all your attempts for this assessment.', 'warning')
        return redirect(url_for('learner_portal.dashboard'))

    if assignment.status in ('passed', 'graded') and assessment.assessment_type == 'quiz':
        flash('You have already completed this assessment.', 'info')
        return redirect(url_for('learner_portal.dashboard'))

    return render_template('assessments/take_quiz.html', assignment=assignment, assessment=assessment)


# ─── Learner: Submit Quiz ───────────────────────────────────────────────────────

@assessments_bp.route('/submit/<int:assignment_id>', methods=['POST'])
@login_required
def submit_quiz(assignment_id):
    """Auto-grade and record a quiz submission."""
    from app.training_management.models import ProgramParticipant
    assignment = AssessmentAssignment.query.get_or_404(assignment_id)
    participant = ProgramParticipant.query.get_or_404(assignment.participant_id)

    if participant.learner_id != current_user.id:
        abort(403)

    assessment = assignment.assessment
    assignment.attempts += 1

    total_points = 0.0
    earned_points = 0.0

    for question in assessment.questions:
        total_points += question.points
        selected_id = request.form.get(f'question_{question.id}')
        selected_option = None
        is_correct = False
        pts = 0.0

        if selected_id:
            selected_option = QuestionOption.query.get(int(selected_id))
            if selected_option and selected_option.is_correct:
                is_correct = True
                pts = question.points
                earned_points += pts

        db.session.add(QuizResponse(
            assignment_id=assignment.id,
            question_id=question.id,
            selected_option_id=selected_option.id if selected_option else None,
            is_correct=is_correct,
            points_awarded=pts
        ))

    score_pct = round((earned_points / total_points * 100) if total_points else 0, 1)
    assignment.score = score_pct
    assignment.raw_points = earned_points
    assignment.max_score = total_points
    assignment.graded_by = 'auto'
    assignment.graded_at = datetime.utcnow()
    assignment.status = 'submitted'

    # Determine pass/fail
    if assessment.assessment_type == 'quiz':
        assignment.status = 'passed' if score_pct >= (assessment.pass_score or 70) else 'failed'

    db.session.commit()

    # Auto-issue certificate if passed
    if assignment.status == 'passed':
        _auto_issue_certificate(assignment)

    flash(
        f'Quiz submitted! You scored {score_pct}% — '
        f'{"🎉 Passed!" if assignment.status == "passed" else "Try again."}',
        'success' if assignment.status == 'passed' else 'warning'
    )
    return redirect(url_for('learner_portal.dashboard'))


# ─── Public: Certificate Verification ──────────────────────────────────────────

@assessments_bp.route('/verify/<string:cert_number>')
def verify_certificate(cert_number):
    """Public-facing certificate verification page."""
    from app.workshops.models import Certificate
    cert = Certificate.query.filter_by(certificate_number=cert_number).first()
    if not cert:
        return render_template('assessments/verify_certificate.html', cert=None, valid=False)
    return render_template('assessments/verify_certificate.html', cert=cert, valid=True)


# ─── Internal: Auto-issue Certificate ──────────────────────────────────────────

def _auto_issue_certificate(assignment: AssessmentAssignment):
    """
    Triggers the background task to issue a certificate.
    """
    from .tasks import issue_certificate_task
    issue_certificate_task.delay(assignment.id)
    current_app.logger.info(f"Queued certificate issuance for assignment {assignment.id}")
