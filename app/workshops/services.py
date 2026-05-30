from datetime import timedelta
from app.core.extensions import db
from .models import Workshop, WorkshopSession

class WorkshopService:
    @staticmethod
    def sync_sessions(workshop: Workshop, form_data: dict):
        """
        Smart sync of sessions. 
        Updates existing sessions, adds new ones, and removes those outside the range.
        Prevents data loss for sessions that stay within the date range.
        """
        start_date = workshop.start_date
        end_date = workshop.end_date
        num_days = (end_date - start_date).days + 1
        
        # Get existing sessions
        existing_sessions = {s.session_number: s for s in workshop.sessions}
        
        # 1. Update or Create sessions for the current range
        for i in range(num_days):
            session_num = i + 1
            session_date = start_date + timedelta(days=i)
            topic = form_data.get(f'session_topic_{i}', f'Day {session_num}')
            
            if session_num in existing_sessions:
                # Update existing
                session = existing_sessions[session_num]
                session.session_date = session_date
                session.topic = topic
                session.start_time = workshop.start_time
                session.end_time = workshop.end_time
            else:
                # Create new
                session = WorkshopSession(
                    session_date=session_date,
                    start_time=workshop.start_time,
                    end_time=workshop.end_time,
                    topic=topic,
                    session_number=session_num
                )
                workshop.sessions.append(session)
        
        # 2. Remove sessions outside the new range
        for session_num, session in existing_sessions.items():
            if session_num > num_days:
                db.session.delete(session)
        
        db.session.flush()
