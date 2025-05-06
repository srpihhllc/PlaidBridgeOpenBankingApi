# PlaidBridgeOpenBankingApi/example_module.py

import logging

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)

class ExampleClass:
    def __init__(self, name="Example"):
        """Initialize the class with a dynamic name."""
        self.name = name
        logging.info(f"ExampleClass initialized with name: {self.name}")

    def greet(self):
        """Return a greeting message."""
        message = f"Hello, {self.name}!"
        logging.info(f"Greet method called: {message}")
        return message

    def change_name(self, new_name):
        """Update the instance's name."""
        logging.info(f"Changing name from {self.name} to {new_name}")
        self.name = new_name
        return f"Name updated to {self.name}"
