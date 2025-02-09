from flask import Flask
from flask_socketio import SocketIO
from .example_module import ExampleClass  # Ensure this path is correct

app = Flask(__name__)
socketio = SocketIO(app)

# Further initialization and routes
# from . import routes  # Uncomment this line if you have a routes module

