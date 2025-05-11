# app.py
import os
import logging
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
from app.s3_utils import download_entire_prefix_from_s3 as download_images
from app.s3_utils import upload_image_to_s3 as upload_image
import shutil
import psycopg2
from psycopg2.extras import register_default_jsonb

s3_bucket_name = "eg-template-matching"
register_default_jsonb()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
CORS(app)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("RDS_HOST"),
        port=os.getenv("RDS_PORT", "5432"),
        dbname=os.getenv("RDS_DBNAME"),
        user=os.getenv("RDS_USER"),
        password=os.getenv("RDS_PASSWORD")
    )

@app.route('/test')
def test():
    return jsonify({"message": "testing, 123. hello from the backend!"}), 200

@app.route('/health')
def health():
    return '', 200

@app.route('/get-sld-and-annotations', methods=['GET'])
def get_sld_and_annotations():
    # 1) Read sld_id from query params
    sld_id = request.args.get('sld_id')
    if not sld_id:
        return jsonify(error="Missing sld_id"), 400

    # 2) Connect to the database
    try:
        conn = get_db_connection()
    except Exception:
        logging.exception("Database connection failed")
        return jsonify(error="Database connection failed"), 500

    try:
        with conn, conn.cursor() as cur:
            # 3) Fetch the base S3 key
            cur.execute(
                "SELECT s3_key FROM slds WHERE sld_id = %s",
                (sld_id,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify(error="SLD not found"), 404
            s3_key = row[0]
            logging.info(f"Fetched S3 key for SLD {sld_id}: {s3_key}")

            # 4) Fetch all non-deleted annotations
            cur.execute("""
                SELECT
                  sld_annotation_id,
                  name,
                  pixel_coords,
                  mask,
                  preview,
                  x, y, width, height
                FROM sld_annotations
                WHERE sld_id = %s
                  AND is_deleted = FALSE
            """, (sld_id,))
            rows = cur.fetchall()

            # 5) Build annotations list
            annotations = []
            for (
                ann_id, name, pixel_coords, mask,
                preview, x, y, width, height
            ) in rows:
                annotations.append({
                    "sld_annotation_id": ann_id,
                    "name":              name,
                    "pixel_coords":      pixel_coords,
                    "mask":              mask,
                    "preview":           preview,
                    "x":                 x,
                    "y":                 y,
                    "width":             width,
                    "height":            height
                })

        # 6) Return both the base key and the annotations array
        return jsonify(
            s3_key=s3_key,
            annotations=annotations
        ), 200

    except Exception:
        logging.exception("Error fetching SLD or annotations")
        return jsonify(error="Internal server error"), 500

if __name__ == '__main__':
    # Use env vars or defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)