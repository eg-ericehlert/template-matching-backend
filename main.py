# main.py
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
                SELECT sld_annotation_id, name, pixel_coords, mask, preview, x, y, width, height, class_type
                FROM sld_annotations
                WHERE sld_id = %s AND is_deleted = FALSE
            """, (sld_id,))
            rows = cur.fetchall()

            # Fetch connections
            cur.execute("""
                SELECT sld_connection_id, source_annotation_id, target_annotation_id
                FROM sld_connections
                WHERE sld_id = %s
            """, (sld_id,))
            connection_rows = cur.fetchall()

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
                "height":              r[8],
                "class_type":          r[9]
            }
            for r in rows
        ]

        connections = [
            {
                "sld_connection_id":     c[0],
                "source_annotation_id":  c[1],
                "target_annotation_id":  c[2]
            }
            for c in connection_rows
        ]

        return jsonify(s3_key=s3_key, annotations=annotations, connections=connections), 200

    except Exception:
        logging.exception("Error fetching SLD, annotations, or connections")
        return jsonify(error="Internal server error"), 500
@app.route('/save-annotation', methods=['POST'])
def save_annotation():
    # 1) Validate payload
    body = request.get_json(silent=True)
    required = [
        "sld_id", "name", "pixel_coords", "mask",
        "preview", "context_snapshot", "x", "y", "width", "height", "type"
    ]
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify(error=f"Missing required fields: {', '.join(missing)}"), 400

    # 2) Extract
    new_id                   = str(uuid.uuid4())
    sld_id                   = body["sld_id"]
    name                     = body["name"]
    asset_class              = body.get("asset_class")
    context_snapshot_dataurl = body["context_snapshot"]  # DataURL or null
    pixel_coords             = body["pixel_coords"]
    mask                     = body["mask"]
    preview_dataurl          = body["preview"]       # DataURL or null
    annotation_type          = body["type"]
    class_type               = body.get("class_type", "default")
    x, y, w, h               = body["x"], body["y"], body["width"], body["height"]
    enclosure_id             = body.get("enclosure_id")

    # 3) Optionally upload preview PNG to S3 and build s3_key
    s3_key = None
    s3_key_context = None
    if preview_dataurl:
        try:
            annotation_id = str(uuid.uuid4())
            header, b64 = preview_dataurl.split(",", 1)
            data = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(data); tmp.flush(); tmp.close()

            object_key = f"annotations/{annotation_id}.png"
            upload_image_to_s3(
                bucket_name=os.getenv("S3_BUCKET"),
                local_path=tmp.name,
                object_key=object_key,
                s3_key=os.getenv("AWS_ACCESS_KEY_ID"),
                s3_secret=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            os.unlink(tmp.name)
            s3_key = f"https://{os.getenv('S3_BUCKET')}.s3.amazonaws.com/{object_key}"
            if context_snapshot_dataurl:
                try:
                    header, b64 = context_snapshot_dataurl.split(",", 1)
                    data = base64.b64decode(b64)
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp.write(data); tmp.flush(); tmp.close()

                    object_key = f"annotations/{annotation_id}_context.png"
                    upload_image_to_s3(
                        bucket_name=os.getenv("S3_BUCKET"),
                        local_path=tmp.name,
                        object_key=object_key,
                        s3_key=os.getenv("AWS_ACCESS_KEY_ID"),
                        s3_secret=os.getenv("AWS_SECRET_ACCESS_KEY")
                    )
                    os.unlink(tmp.name)
                    s3_key_context = f"https://{os.getenv('S3_BUCKET')}.s3.amazonaws.com/{object_key}"
                except Exception:
                    logging.exception("Failed to upload context snapshot to S3")
                    # continue without s3_key
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
                   asset_class,
                   pixel_coords,
                   mask,
                   preview,    -- raw DataURL, if you still want it
                   context_snapshot,
                   s3_key,     -- new column
                   s3_key_context,
                   x, y, width, height,
                   annotation_type,
                   is_deleted,
                   class_type,
                   enclosure_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                RETURNING sld_annotation_id
            """, (
                new_id,
                sld_id,
                name,
                asset_class,
                psycopg2.extras.Json(pixel_coords),
                psycopg2.extras.Json(mask),
                preview_dataurl,
                context_snapshot_dataurl,
                s3_key,
                s3_key_context,         
                x, y, w, h,
                annotation_type,
                class_type,
                enclosure_id
            ))
            saved_id = cur.fetchone()[0]
            logging.info(f"Saved annotation {saved_id} for SLD {sld_id}")

        return jsonify(
            message="Annotation saved",
            sld_annotation_id=saved_id,
            name=name,
            asset_class=asset_class,
            class_type=class_type,
            enclosure_id=enclosure_id
        ), 201

    except Exception:
        logging.exception("Error saving annotation")
        return jsonify(error="Internal server error"), 500

@app.route('/save-connections', methods=['POST'])
def save_connections():
    # 1) Validate payload
    body = request.get_json(silent=True)
    if not body:
        return jsonify(error="Invalid JSON payload"), 400
    
    required = ["sld_id", "connections"]
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify(error=f"Missing required fields: {', '.join(missing)}"), 400
    
    # Validate connections array
    connections = body["connections"]
    if not isinstance(connections, list):
        return jsonify(error="Connections must be an array"), 400
    
    if not connections:
        return jsonify(message="No connections to save"), 200
    
    # Check each connection has required fields
    connection_fields = ["connection_id", "source_annotation_id", "target_annotation_id"]
    for i, conn in enumerate(connections):
        if not isinstance(conn, dict):
            return jsonify(error=f"Connection at index {i} is not an object"), 400
        
        missing_fields = [f for f in connection_fields if f not in conn]
        if missing_fields:
            return jsonify(error=f"Connection at index {i} is missing fields: {', '.join(missing_fields)}"), 400
    
    # 2) Extract
    sld_id = body["sld_id"]
    
    # 3) Insert into DB
    try:
        conn = get_db_connection()
    except Exception:
        logging.exception("DB connection failed")
        return jsonify(error="Database connection failed"), 500
    
    try:
        with conn, conn.cursor() as cur:
            # First, delete existing connections for this SLD
            cur.execute("""
                DELETE FROM sld_connections
                WHERE sld_id = %s
            """, (sld_id,))
            
            # Then insert all new connections
            saved_ids = []
            for connection in connections:
                connection_id = connection.get("connection_id") or str(uuid.uuid4())
                source_id = connection["source_annotation_id"]
                target_id = connection["target_annotation_id"]
                source_enclosure_id = connection.get("source_enclosure_id")
                target_enclosure_id = connection.get("target_enclosure_id")
                
                cur.execute("""
                    INSERT INTO sld_connections
                      (sld_connection_id,
                       sld_id,
                       source_annotation_id,
                       target_annotation_id,
                       source_enclosure_id,
                       target_enclosure_id
                            )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sld_connection_id) DO UPDATE
                    SET source_annotation_id = EXCLUDED.source_annotation_id,
                        target_annotation_id = EXCLUDED.target_annotation_id
                    RETURNING sld_connection_id
                """, (
                    connection_id,
                    sld_id,
                    source_id,
                    target_id,
                    source_enclosure_id,
                    target_enclosure_id
                ))
                saved_id = cur.fetchone()[0]
                saved_ids.append(saved_id)
            
            logging.info(f"Saved {len(saved_ids)} connections for SLD {sld_id}")
            
        return jsonify(
            message=f"Successfully saved {len(saved_ids)} connections",
            connection_ids=saved_ids,
            sld_id=sld_id,
            success=True
        ), 201
        
    except Exception as e:
        logging.exception("Error saving connections")
        return jsonify(error=f"Internal server error: {str(e)}"), 500
    
if __name__ == '__main__':
    # Use env vars or defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)