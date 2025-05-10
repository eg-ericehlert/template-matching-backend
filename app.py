# app.py
import os
import logging
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
from s3_utils import download_entire_prefix_from_s3 as download_images
from s3_utils import upload_image_to_s3 as upload_image
import shutil

s3_bucket_name = "eg-template-matching"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)

@app.route('/test')
def test():
    return jsonify({"message": "testing, 123. hello from the backend!"}), 200

@app.route('/health')
def health():
    return '', 200

if __name__ == '__main__':
    # Use env vars or defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)