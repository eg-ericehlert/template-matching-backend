# app.py
from flask import Flask
from flask_cors import CORS
import os
import templatematch

app = Flask(__name__)
CORS(app)   # <-- this opens all origins; you can lock it down if you like

@app.route('/hello')
def hello():
    return "hello guvvvnaaaa"

@app.route('/match_template', methods=['POST'])
def match_template():
    data = request.get_json(force=True)
    input_dir = data.get('dir')
    base_file = data.get('base_filename')

    if not input_dir or not base_file:
        return jsonify({"error": "Both 'dir' and 'base_filename' are required"}), 400

    full_dir = os.path.abspath(input_dir)
    if not os.path.isdir(full_dir):
        return jsonify({"error": f"Directory not found: {full_dir}"}), 404
    
    try:
        result = templatematch.run_job(full_dir, base_file)
        return jsonify(result)
    except FileNotFoundError as fnf:
        return jsonify({"error": str(fnf)}), 404
    except Exception as e:
        app.logger.exception("Error during template matching")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
