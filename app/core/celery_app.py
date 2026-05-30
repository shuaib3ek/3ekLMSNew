from celery import Celery
from celery.schedules import crontab
import os

def make_celery(app):
    """
    Bind Celery to the Flask app context.
    Configures the broker, backend, and the periodic task schedule (Beat).
    """
    celery = Celery(
        app.import_name,
        broker=app.config['REDIS_URL'],
        backend=app.config['REDIS_URL']
    )
    
    celery.conf.update(
        # Use UTC internally
        timezone='Asia/Kolkata',
        enable_utc=True,

        # Retry on connection failure
        broker_connection_retry_on_startup=True,

        # Task result expiry (keep results for 1 hour)
        result_expires=3600,

        # Auto-discover tasks from these modules
        include=[
            'app.workshops.tasks',
            'app.crm_client.sync_tasks',
            'app.assessments.tasks',
            'app.core.tasks',
        ],

        # ─── Beat Schedule (Periodic Tasks) ─────────────────────────────
        beat_schedule={
            'msteams-processor-every-2-min': {
                'task': 'app.workshops.tasks.process_msteams_tasks',
                'schedule': 120.0,   # every 120 seconds
            },
            'crm-daily-sync': {
                'task': 'app.crm_client.sync_tasks.sync_all_crm_data',
                'schedule': crontab(hour=2, minute=0),  # 2 AM IST daily
            },
        },
    )

    # Ensure tasks run inside the Flask application context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    
    # Store the celery instance in app.extensions for easy access
    if not hasattr(app, 'extensions'):
        app.extensions = {}
    app.extensions['celery'] = celery
    
    return celery
