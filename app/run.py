# run.py
from app import create_app, socketio, db
import os

app = create_app()

with app.app_context():
    db.create_all()  # Create tables if they don't exist

if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
