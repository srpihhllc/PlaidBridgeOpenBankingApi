from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

# Custom error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Custom error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Custom maintenance page
@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html')

if __name__ == "__main__":
    app.run()
