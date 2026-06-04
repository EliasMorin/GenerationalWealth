"""
Entry point for the Generational Wealth application.
This replaces the large backend.py file with a modular structure.
"""

from app import create_app

# Create the Flask application instance using the factory pattern
app = create_app()

if __name__ == '__main__':
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=True)