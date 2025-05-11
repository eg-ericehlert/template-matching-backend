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
import uuid

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

@app.route('/get-sld-and-annotations', methods=['POST'])
def get_sld_and_annotations():
    body = request.get_json(silent=True)
    if not body or 'sld_id' not in body:
        return jsonify(error="Missing sld_id in request body"), 400
    sld_id = body['sld_id']

    try:
        conn = get_db_connection()
    except Exception:
        logging.exception("Database connection failed")
        return jsonify(error="Database connection failed"), 500

    try:
        with conn, conn.cursor() as cur:
            # Fetch base image key
            cur.execute("SELECT s3_key FROM slds WHERE sld_id = %s", (sld_id,))
            row = cur.fetchone()
            if not row:
                return jsonify(error="SLD not found"), 404
            s3_key = row[0]

            # Fetch annotations
            cur.execute("""
                SELECT sld_annotation_id, name, pixel_coords, mask, preview, x, y, width, height
                FROM sld_annotations
                WHERE sld_id = %s AND is_deleted = FALSE
            """, (sld_id,))
            rows = cur.fetchall()

        annotations = [
            {
                "sld_annotation_id":   r[0],
                "name":                r[1],
                "pixel_coords":        r[2],
                "mask":                r[3],
                "preview":             r[4],
                "x":                   r[5],
                "y":                   r[6],
                "width":               r[7],
                "height":              r[8]
            }
            for r in rows
        ]

        return jsonify(s3_key=s3_key, annotations=annotations), 200

    except Exception:
        logging.exception("Error fetching SLD or annotations")
        return jsonify(error="Internal server error"), 500

@app.route('/save-annotation', methods=['POST'])
def save_annotation():
    body = request.get_json(silent=True)
    required = ["sld_id", "name", "pixel_coords", "mask", "preview", "x", "y", "width", "height", "type"]
    if not body or any(key not in body for key in required):
        return jsonify(error=f"Missing one of required fields: {', '.join(required)}"), 400

    # 1) generate a new UUID
    new_id = str(uuid.uuid4())

    # 2) extract fields
    sld_id       = body["sld_id"]
    name         = body["name"]
    pixel_coords = body["pixel_coords"]
    mask         = body["mask"]
    preview      = body["preview"]
    x            = body["x"]
    y            = body["y"]
    width        = body["width"]
    height       = body["height"]
    type         = body["type"]

    # 3) connect
    try:
        conn = get_db_connection()
    except Exception:
        logging.exception("Database connection failed")
        return jsonify(error="Database connection failed"), 500

    # 4) insert
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sld_annotations
                  (sld_annotation_id,
                   sld_id,
                   name,
                   pixel_coords,
                   mask,
                   preview,
                   x,
                   y,
                   width,
                   height,
                   type, 
                   is_deleted)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                RETURNING sld_annotation_id
            """, (
                new_id,
                sld_id,
                name,
                psycopg2.extras.Json(pixel_coords),
                psycopg2.extras.Json(mask),
                preview,
                x,
                y,
                width,
                height,
                type
            ))
            saved_id = cur.fetchone()[0]
            logging.info(f"Inserted annotation {saved_id} for SLD {sld_id}")

        return jsonify(
            message="Annotation saved",
            sld_annotation_id=saved_id
        ), 201

    except Exception:
        logging.exception("Error saving annotation")
        return jsonify(error="Internal server error"), 500

if __name__ == '__main__':
    # Use env vars or defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)