#!/bin/bash

# Create the static directory if it doesn't exist
mkdir -p static

# Create the styles.css file with default content
cat <<EOL > static/styles.css
body {
    font-family: Arial, sans-serif;
    background-color: #333;
    color: white;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    margin: 0;
}

.login-container {
    background-color: #222;
    padding: 20px;
    border-radius: 5px;
    width: 300px;
    text-align: center;
}

.login-container h2 {
    margin-bottom: 10px;
}

.login-container p {
    margin-bottom: 20px;
}

.login-container label {
    display: block;
    text-align: left;
    margin-bottom: 5px;
}

.login-container input[type="email"],
.login-container input[type="password"] {
    width: calc(100% - 20px);
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 5px;
    border: none;
    background-color: #444;
    color: white;
}

.login-container .checkbox-container {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.login-container .checkbox-container input {
    margin-right: 5px;
}

.login-container .forgot-password {
    display: block;
    margin-bottom: 20px;
    color: #0d6efd;
    text-decoration: none;
}

.login-container button {
    width: 100%;
    padding: 10px;
    background-color: #0d6efd;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}

.login-container button:hover {
    background-color: #0056b3;
}

.login-container .signup {
    margin-top: 20px;
}

.login-container .signup a {
    color: #0d6efd;
    text-decoration: none;
}
EOL

# Create the statements directory if it doesn't exist
mkdir -p statements

echo "Setup complete. The static and statements directories have been created."
