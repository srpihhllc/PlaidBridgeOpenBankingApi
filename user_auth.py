class User:
    def __init__(self, id, username=None, verified=False):
        self.id = id
        self.username = username
        self.verified = verified

    @staticmethod
    def authenticate(username, password):
        # Example user lookup; replace with a secure lookup from your DB.
        # Here, we simulate a lender ("test_user") who must be verified.
        user_data = {
            "username": "test_user",
            "password": "test_password",
            "verified": False  # Initially, the lender is not verified.
        }
        
        if username == user_data["username"] and password == user_data["password"]:
            return User("1", username=user_data["username"], verified=user_data["verified"])
        
        return None
