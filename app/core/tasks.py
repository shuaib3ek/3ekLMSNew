from flask import current_app, render_template
from celery import shared_task
from datetime import datetime
from app.core.extensions import db

@shared_task(bind=True, max_retries=3)
def send_transactional_email_task(self, recipient_email, subject, template_name, **kwargs):
    """
    Background task to send one-off transactional emails via MS Graph.
    """
    from app.services.ms_graph_service import MSGraphService
    
    try:
        graph = MSGraphService()
        html_body = render_template(template_name, now=datetime.utcnow(), **kwargs)
        
        sent = graph.send_email(
            recipient_email, 
            subject, 
            html_body,
            sender_email=kwargs.get('sender_email')
        )
        
        if not sent:
            raise Exception("MS Graph returned failure status for email delivery.")
            
        return f"Email '{subject}' sent to {recipient_email}."
        
    except Exception as e:
        current_app.logger.error(f"Failed to send transactional email to {recipient_email}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=2)
def generate_workshop_meeting_task(self, workshop_id):
    """
    Background task to generate a Microsoft Teams meeting for a workshop.
    """
    from app.workshops.models import Workshop
    from app.services.ms_graph_service import MSGraphService
    
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return f"Workshop {workshop_id} not found."
        
    if workshop.meeting_link:
        return f"Meeting already exists for workshop {workshop_id}."

    try:
        def parse_time_str(ts):
            parts = ts.split(' ')
            if len(parts) >= 2 and parts[1].upper() in ['AM', 'PM']:
                return datetime.strptime(f"{parts[0]} {parts[1]}", '%I:%M %p').time()
            return datetime.strptime(parts[0], '%H:%M').time()

        start_dt = datetime.combine(workshop.start_date, parse_time_str(workshop.start_time))
        end_dt = datetime.combine(workshop.end_date, parse_time_str(workshop.end_time))
        
        graph = MSGraphService()
        meeting = graph.create_online_meeting(workshop.title, start_dt, end_dt)
        
        if meeting and 'joinWebUrl' in meeting:
            workshop.meeting_link = meeting['joinWebUrl']
            db.session.commit()
            return f"Meeting link generated for workshop {workshop_id}."
        else:
            raise Exception("MS Graph failed to return a join URL.")
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Meeting generation failed for workshop {workshop_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)
