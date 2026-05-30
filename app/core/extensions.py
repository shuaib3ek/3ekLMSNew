"""
LMS Core Extensions
Initialised here, bound to app in create_app().
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
