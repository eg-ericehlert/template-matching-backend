# app.py

import os
import logging
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import templatematch

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)

@app.route('/hello')
def hello():
    return "hello guvvvnaaaa"

@app.route('/match_template', methods=['POST'])
def match_template():
    # Make sure we imported `request` above
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
    except Exception:
        app.logger.exception("Error during template matching")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Use env vars or defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)