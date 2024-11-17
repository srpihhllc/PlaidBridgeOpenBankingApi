from flask import Flask, render_template, request, jsonify, send_from_directory
from jinja2.utils import escape

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

if __name__ == "__main__":
    app.run()
