from flask import Blueprint

learners_bp = Blueprint('learners', __name__, template_folder='../templates')

from . import routes
