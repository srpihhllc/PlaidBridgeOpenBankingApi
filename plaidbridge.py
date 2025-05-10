from flask import Flask, jsonify, request
import os

# Initialize Flask app
app = Flask(__name__)

# Sample route to verify the app is running
@app.route("/")
def home():
    return jsonify({"message": "Welcome to PlaidBridge API!"})

# Example route to check service health
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# Example environment variable usage
@app.route("/config", methods=["GET"])
def config():
    return jsonify({
        "PLATFORM": os.getenv("PLATFORM", "development"),
        "VERSION": "1.0.0"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
