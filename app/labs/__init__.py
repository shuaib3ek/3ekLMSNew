from flask import Blueprint

labs_bp = Blueprint('labs', __name__, template_folder='../templates')

from . import routes, models
