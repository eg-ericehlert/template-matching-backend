# app.py
import os
import logging
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
from app.s3_utils import download_entire_prefix_from_s3 as download_images
from app.s3_utils import upload_image_to_s3
import shutil
import base64
import tempfile
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
    # 1) Validate payload
    body = request.get_json(silent=True)
    required = [
        "sld_id", "name", "pixel_coords", "mask",
        "preview", "x", "y", "width", "height", "annotation_type"
    ]
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify(error=f"Missing required fields: {', '.join(missing)}"), 400

    # 2) Extract
    new_id           = str(uuid.uuid4())
    sld_id           = body["sld_id"]
    name             = body["name"]
    pixel_coords     = body["pixel_coords"]
    mask             = body["mask"]
    preview_dataurl  = body["preview"]       # DataURL or null
    annotation_type  = body["annotation_type"]
    x, y, w, h       = body["x"], body["y"], body["width"], body["height"]

    # 3) Optionally upload preview PNG to S3 and build s3_key
    s3_key = None
    if preview_dataurl:
        try:
            header, b64 = preview_dataurl.split(",", 1)
            data = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(data); tmp.flush(); tmp.close()

            object_key = f"annotations/{uuid.uuid4()}.png"
            upload_image_to_s3(
                bucket_name=os.getenv("S3_BUCKET"),
                local_path=tmp.name,
                object_key=object_key,
                s3_key=os.getenv("AWS_ACCESS_KEY_ID"),
                s3_secret=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            os.unlink(tmp.name)
            s3_key = f"https://{os.getenv('S3_BUCKET')}.s3.amazonaws.com/{object_key}"
        except Exception:
            logging.exception("Failed to upload preview to S3")
            # continue without s3_key

    # 4) Insert into DB
    try:
        conn = get_db_connection()
    except Exception:
        logging.exception("DB connection failed")
        return jsonify(error="Database connection failed"), 500

    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sld_annotations
                  (sld_annotation_id,
                   sld_id,
                   name,
                   pixel_coords,
                   mask,
                   preview,    -- raw DataURL, if you still want it
                   s3_key,     -- new column
                   x, y, width, height,
                   annotation_type,
                   is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                RETURNING sld_annotation_id
            """, (
                new_id,
                sld_id,
                name,
                psycopg2.extras.Json(pixel_coords),
                psycopg2.extras.Json(mask),
                preview_dataurl,
                s3_key,
                x, y, w, h,
                annotation_type
            ))
            saved_id = cur.fetchone()[0]
            logging.info(f"Saved annotation {saved_id} for SLD {sld_id}")

        return jsonify(
            message="Annotation saved",
            sld_annotation_id=saved_id,
            s3_key=s3_key
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