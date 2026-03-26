from flask import Blueprint

assessments_bp = Blueprint('assessments', __name__, template_folder='../templates')

from . import routes, models
