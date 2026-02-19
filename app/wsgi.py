# This file contains the WSGI configuration required to serve up your
# web application at http://srpihhllc.pythonanywhere.com/
# It works by setting the variable 'application' to a WSGI handler of some
# description.

import sys
import os

# ✅ Add your project directory to the sys.path
project_home = '/home/srpihhllc/PlaidBridgeOpenBankingApi'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ✅ Ensure PythonAnywhere recognizes the correct Flask package
os.environ["PYTHONPATH"] = project_home

# ✅ Import Flask app using the correct package name
from app import create_app

# ✅ Set up WSGI application instance
application = create_app()
