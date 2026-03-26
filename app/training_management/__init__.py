from flask import Blueprint

training_bp = Blueprint('training_management', __name__, template_folder='../templates')

from . import routes, models
