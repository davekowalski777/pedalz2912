import os
import sys

# Set environment variables
os.environ['SECRET_KEY'] = '6bbdf0e87654c98c0c75eacacc60bafa77539717df0f863f17ccf10784ad3250'
os.environ['DATABASE_URL'] = 'sqlite:///pedals.db'
os.environ['FLASK_ENV'] = 'production'

# Add your project directory to the sys.path
project_home = '/home/davekowalski777/pedalz2912'  # Update with your PythonAnywhere username
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import your Flask app
from app import app as application

if __name__ == '__main__':
    application.run()
