from flask import Blueprint

organizations_bp = Blueprint('organizations', __name__)

from . import models, routes
