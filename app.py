"""
Flask web application for URL generator.
"""

from flask import Flask
import sys
from pathlib import Path

import re
# ...

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.blueprints.main import main_bp
from src.blueprints.tracking import tracking_bp
from src.blueprints.dashboard import dashboard_bp
from src.blueprints.api import api_bp
from src.blueprints.analysis import analysis_bp
from src.modules.therapist import therapist_bp
from src.modules.surveys import surveys_bp
from src.modules.conversations import conversations_bp

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change in production
    
    # Manual CORS handling - simpler and more reliable
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        # Allow requests from dnstrainer.com and all subdomains
        if origin and (origin == 'https://dnstrainer.com' or 
                      origin == 'https://booking.dnstrainer.com' or
                      origin == 'http://localhost:5000' or
                      origin.endswith('.dnstrainer.com')):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    # Handle OPTIONS requests explicitly
    @app.route('/track', methods=['OPTIONS'])
    def track_options():
        return '', 200
    
    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(tracking_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(therapist_bp)
    app.register_blueprint(surveys_bp)
    app.register_blueprint(conversations_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

