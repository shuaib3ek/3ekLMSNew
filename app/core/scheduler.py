from datetime import datetime
from flask_apscheduler import APScheduler

scheduler = APScheduler()


def init_scheduler(app):
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Kolkata'

    from app.workshops.tasks import process_msteams_tasks, renew_msteams_subscriptions

    scheduler.init_app(app)

    import os
    import sys

    # Only start scheduler once (handles Flask reloader)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        scheduler.start()
        print('--- LMS Scheduler Started ---', flush=True)
    else:
        print('LMS Scheduler: Waiting for reloader child process...', flush=True)

    # MS Teams background task engine — every 2 minutes
    @scheduler.task('interval', id='lms_msteams_processor', minutes=2, misfire_grace_time=60)
    def job_msteams_processor():
        with app.app_context():
            process_msteams_tasks()

    # CRM Background Sync — every 24 hours
    @scheduler.task('interval', id='lms_crm_daily_sweep', days=1, misfire_grace_time=3600)
    def job_crm_daily_sweep():
        from app.crm_client.sync_tasks import sync_all_crm_data
        with app.app_context():
            sync_all_crm_data()

    # Trigger initial sync on startup after a 5 second delay
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        import threading
        import time
        
        def initial_sync_delayed():
            time.sleep(5)
            from app.crm_client.sync_tasks import sync_all_crm_data
            with app.app_context():
                try:
                    sync_all_crm_data()
                except Exception as e:
                    print(f"[LMS] Initial Sync Failed: {e}", flush=True)

        threading.Thread(target=initial_sync_delayed, daemon=True).start()

    print('--- LMS Scheduler Initialised (Timezone: Asia/Kolkata) ---')
