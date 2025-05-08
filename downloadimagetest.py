import boto3
import logging
import os

def download_image_from_s3(bucket_name, object_key, local_path, s3_key=None, s3_secret=None):

    """
    Download an image from S3 bucket to a local path.
    """
    
    s3 = boto3.client('s3', aws_access_key_id=s3_key, aws_secret_access_key=s3_secret)
    try:
        s3.download_file(bucket_name, object_key, local_path)
        logging.info(f"Downloaded {object_key} from bucket {bucket_name} to {local_path}")
    except Exception as e:
        logging.error(f"Failed to download {object_key} from bucket {bucket_name}: {e}")

# test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    bucket_name = 'eg-template-matching'
    object_key = 'results.png'
    local_path = os.path.join(os.getcwd(), 'downloaded_image2.jpg')
    
    download_image_from_s3(bucket_name, object_key, local_path, 
                            s3_key=os.getenv('AWS_ACCESS_KEY_ID'), 
                            s3_secret=os.getenv('AWS_SECRET_ACCESS_KEY'))