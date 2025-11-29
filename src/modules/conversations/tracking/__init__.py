from flask import Blueprint

tracking_bp = Blueprint('tracking', __name__, url_prefix='/api/tracking')

from . import routes
