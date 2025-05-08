# app.py
# Simple Flask application that returns "hello" at the /hello route

from flask import Flask

app = Flask(__name__)

@app.route('/hello')
def hello():
    return "hello"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
