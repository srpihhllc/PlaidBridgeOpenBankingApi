import os
import sys

# Ensure the project root directory is in sys.path so the "app" package can be found.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Attempt to import the application factory and the database object from the app package.
try:
    from app import create_app, socketio, db  # ✅ Added `socketio`
except ImportError as e:
    print("Error importing from app:", e)
    sys.exit(1)

# Create the Flask application using the factory function.
app = create_app()

# Within the app context, create the database tables (if they don't already exist).
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    # Read configuration values (port and debug flag) from the environment,
    # offering default values if the environment variables are not set.
    port = int(os.environ.get("PORT", 5000))  # ✅ Changed default port to 5000
    debug = os.environ.get("DEBUG", "False").lower() in ["true", "1", "yes"]

    # Run Flask-SocketIO server instead of default Flask `app.run()`
    socketio.run(app, host="0.0.0.0", port=port, debug=True)  # ✅ Updated
