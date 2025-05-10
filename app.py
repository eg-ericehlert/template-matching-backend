# app.py
import os
import logging
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import templatematch
from s3_utils import download_entire_prefix_from_s3 as download_images
from s3_utils import upload_image_to_s3 as upload_image
import shutil

s3_bucket_name = "eg-template-matching"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)

@app.route('/hello')
def hello():
    return "hello guvvvnaaaa"

@app.route('/health')
def health():
    return '', 200

# @app.route('/match_template', methods=['POST'])
# def match_template():
#     data = request.get_json(force=True)
#     input_dir = data.get('dir')
#     base_file = data.get('base_filename')

#     if not input_dir or not base_file:
#         return jsonify({"error": "Both 'dir' and 'base_filename' are required"}), 400

#     # Download the base file from S3
#     download_images(bucket_name=s3_bucket_name, prefix=input_dir, local_base=input_dir, 
#                             s3_key=os.getenv('AWS_ACCESS_KEY_ID'), 
#                             s3_secret=os.getenv('AWS_SECRET_ACCESS_KEY'))
    
#     full_dir = os.path.abspath(input_dir)
#     if not os.path.isdir(full_dir):
#         return jsonify({"error": f"Directory not found: {full_dir}"}), 404

#     try:
#         result = templatematch.run_job(full_dir, base_file)
#         results_image = os.path.join(input_dir, 'results.png')
#         counts_image = os.path.join(input_dir, 'annotation_counts.png')
#         upload_image(bucket_name=s3_bucket_name, local_path=results_image, 
#                             object_key=os.path.join(input_dir, 'results.png'), 
#                             s3_key=os.getenv('AWS_ACCESS_KEY_ID'), 
#                             s3_secret=os.getenv('AWS_SECRET_ACCESS_KEY'))
#         upload_image(bucket_name=s3_bucket_name, local_path=counts_image,
#                             object_key=os.path.join(input_dir, 'annotation_counts.png'), 
#                             s3_key=os.getenv('AWS_ACCESS_KEY_ID'), 
#                             s3_secret=os.getenv('AWS_SECRET_ACCESS_KEY'))
#         # Clean up local files
#         os.remove(results_image)
#         os.remove(counts_image)

#         try:
#             shutil.rmtree(full_dir)
#             app.logger.info(f"Removed directory: {full_dir}")
#         except Exception as e:
#             app.logger.error(f"Failed to remove directory {full_dir}: {e}")

#         # Return the result
#         return jsonify(result)
    
#     except FileNotFoundError as fnf:
#         return jsonify({"error": str(fnf)}), 404
#     except Exception:
#         app.logger.exception("Error during template matching")
#         return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Use env vars or defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)