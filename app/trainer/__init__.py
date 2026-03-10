from flask import Blueprint

trainer_portal_bp = Blueprint('trainer_portal', __name__, url_prefix='/trainer')

from app.trainer import routes
