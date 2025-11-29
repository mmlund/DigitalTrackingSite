from flask import Blueprint

therapist_bp = Blueprint('therapist', __name__, url_prefix='/api/therapist')

from . import routes
