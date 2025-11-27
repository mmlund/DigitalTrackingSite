from flask import Blueprint, render_template
from src.config import get_utm_sources, get_utm_mediums, is_test_mode
from src.mock_data_generator import get_example_placeholders

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the main form page."""
    utm_sources = get_utm_sources()
    utm_mediums = get_utm_mediums()
    test_mode = is_test_mode()
    mock_data = {}
    
    if test_mode:
        mock_data = {
            "example_placeholders": get_example_placeholders(),
            "test_mode": True
        }
    else:
        mock_data = {
            "test_mode": False
        }
    
    return render_template('index.html', 
                         utm_sources=utm_sources, 
                         utm_mediums=utm_mediums,
                         test_mode=test_mode,
                         mock_data=mock_data)
