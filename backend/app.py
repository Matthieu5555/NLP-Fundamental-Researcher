"""
Flask application entry point for George Financial Analyst.

This module sets up the Flask server with CORS support, SSE streaming,
and routes for stock analysis and chat functionality.
"""

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import API blueprints
from api.analysis import analysis_bp
from api.chat import chat_bp
from api.reports import reports_bp

def create_app():
    """
    Application factory function.

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
            "methods": ["GET", "POST", "DELETE"],
            "allow_headers": ["Content-Type"]
        }
    })

    # Register blueprints
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')

    # Health check endpoint
    @app.route('/')
    def home():
        return {'status': 'ok', 'message': 'George Financial Analyst API'}

    @app.route('/health')
    def health():
        return {'status': 'healthy', 'version': '2.0.0'}

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'

    print(f"Starting George Financial Analyst API on port {port}")
    app.run(debug=debug, port=port, host='0.0.0.0')
