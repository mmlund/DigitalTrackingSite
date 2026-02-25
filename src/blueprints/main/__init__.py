from flask import Blueprint, render_template, redirect, url_for
from src.config import get_utm_sources, get_utm_mediums, is_test_mode
from src.mock_data_generator import get_example_placeholders

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Redirect to Campaign Tracker (primary entry point)."""
    return redirect(url_for('campaigns.campaign_list_page'))

