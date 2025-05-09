# download_image_from_s3.py
import boto3
import logging
import os

def download_image_from_s3(bucket_name, object_key, local_path, s3_key=None, s3_secret=None):

    """
    Download an image from S3 bucket to a local path.
    """
    local_dir = os.path.dirname(local_path)
    if local_dir and not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
    
    s3 = boto3.client('s3', aws_access_key_id=s3_key, aws_secret_access_key=s3_secret)
    try:
        s3.download_file(bucket_name, object_key, local_path)
        logging.info(f"Downloaded {object_key} from bucket {bucket_name} to {local_path}")
    except Exception as e:
        logging.error(f"Failed to download {object_key} from bucket {bucket_name}: {e}")

def download_entire_prefix_from_s3(bucket_name, prefix, local_base, s3_key=None, s3_secret=None):
    """
    Download all objects from S3 under the given prefix into local_base/,
    recreating the sub-folder structure but skipping directory placeholders.
    """
    os.makedirs(local_base, exist_ok=True)

    s3 = boto3.client(
        's3',
        aws_access_key_id=s3_key,
        aws_secret_access_key=s3_secret
    )

    paginator = s3.get_paginator('list_objects_v2')
    prefix = prefix.rstrip('/') + '/'

    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']

            # Skip any “directory” placeholder (size 0 and ending with '/')
            if key.endswith('/') or obj.get('Size', 0) == 0:
                continue

            # derive the path inside the prefix
            rel_path = key[len(prefix):]
            local_path = os.path.join(local_base, rel_path)

            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            try:
                s3.download_file(bucket_name, key, local_path)
                logging.info(f"Downloaded s3://{bucket_name}/{key} → {local_path}")
            except Exception as e:
                logging.error(f"Failed to download {key}: {e}")
            key = obj['Key']
            # derive the path inside the prefix
            rel_path = key[len(prefix):]
            if not rel_path:  # skip the “folder” key itself
                continue

            local_path = os.path.join(local_base, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            try:
                s3.download_file(bucket_name, key, local_path)
                logging.info(f"Downloaded s3://{bucket_name}/{key} → {local_path}")
            except Exception as e:
                logging.error(f"Failed to download {key}: {e}")
            key = obj['Key']
            # compute the relative path under the prefix
            rel_path = key[len(prefix.rstrip('/') + '/'):]

            # skip "prefix/" itself if it's listed
            if not rel_path:
                continue

            # local file path
            local_path = os.path.join(local_base, rel_path)
            # ensure containing folder exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # download the single file
            s3.download_file(bucket_name, key, local_path)
            logging.info(f"Downloaded {key} to {local_path}")

# test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    bucket_name = 'eg-template-matching'
    object_key = 'results.png'
    local_path = os.path.join(os.getcwd(), 'downloaded_image2.jpg')

    # Download a folder
    prefix = '1746729918481'
    local_base = os.path.join(os.getcwd(), 'downloaded_folder')
    download_entire_prefix_from_s3(bucket_name, prefix, local_base, 
                            s3_key=os.getenv('AWS_ACCESS_KEY_ID'), 
                            s3_secret=os.getenv('AWS_SECRET_ACCESS_KEY'))