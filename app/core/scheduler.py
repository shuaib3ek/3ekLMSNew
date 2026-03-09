from flask_apscheduler import APScheduler

scheduler = APScheduler()


def init_scheduler(app):
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Kolkata'

    from app.workshops.tasks import process_msteams_tasks, renew_msteams_subscriptions

    scheduler.init_app(app)

    import os
    import sys

    is_run_py = 'run.py' in sys.argv[0]
    is_reloader_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

    if is_run_py and not is_reloader_child:
        print('LMS Scheduler: Skipping start in reloader main process.')
    else:
        scheduler.start()

    # MS Teams background task engine — every 2 minutes
    @scheduler.task('interval', id='lms_msteams_processor', minutes=2, misfire_grace_time=60)
    def job_msteams_processor():
        with app.app_context():
            process_msteams_tasks()

    # MS Teams subscription renewal — every 12 hours
    @scheduler.task('interval', id='lms_msteams_renew', hours=12, misfire_grace_time=3600)
    def job_msteams_renew():
        with app.app_context():
            renew_msteams_subscriptions()

    print('--- LMS Scheduler Initialised (Timezone: Asia/Kolkata) ---')
