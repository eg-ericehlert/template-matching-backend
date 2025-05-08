# app.py
# Simple Flask application that returns "hello" at the /hello route

from flask import Flask

app = Flask(__name__)

@app.route('/hello')
def hello():
    return "hello"

if __name__ == '__main__':
    # Run the development server on localhost:5000
    app.run(debug=True)
