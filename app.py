from flask import Flask, render_template, request, jsonify, send_from_directory
from jinja2.utils import escape

# Create an instance of the Flask class
app = Flask(__name__)

# Define a route for the root URL
@app.route('/')
def index():
    return "Hello, World!"

# Add your other routes and logic here

# Check if the script is run directly (and not imported), then run the app
if __name__ == "__main__":
    app.run()
