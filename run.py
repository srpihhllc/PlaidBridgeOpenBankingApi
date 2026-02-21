# /home/srpihhllc/PlaidBridgeOpenBankingApi/run.py

import os
import sys


def main() -> None:
    project_root = os.path.abspath(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from app import create_app, db, socketio

    app = create_app()

    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"DB Skip: {e}")

    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
