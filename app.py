from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)   # <-- this opens all origins; you can lock it down if you like

@app.route('/hello')
def hello():
    return "hello"