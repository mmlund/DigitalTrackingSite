"""
Flask web application for URL generator.
"""

from flask import Flask
import sys
from pathlib import Path

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
    
    # Enable CORS for specific domains
    from flask_cors import CORS
    CORS(app, resources={
        r"/track": {"origins": ["https://dnstrainer.com", "https://booking.dnstrainer.com", "http://localhost:5000", "https://*.dnstrainer.com"]},
        r"/api/*": {"origins": ["https://dnstrainer.com", "https://booking.dnstrainer.com", "http://localhost:5000", "https://*.dnstrainer.com"]}
    })
    
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

