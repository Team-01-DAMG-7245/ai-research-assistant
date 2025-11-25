"""
S3 Client Utility
Handles all S3 operations for the project
"""

import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

load_dotenv()

class S3Client:
    """Wrapper for S3 operations"""
    
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET_NAME')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.s3 = boto3.client('s3', region_name=self.region)
        self.logger = logging.getLogger(__name__)
    
    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """
        Upload a file to S3
        
        Args:
            local_path: Path to local file
            s3_key: S3 key (path in bucket)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3.upload_file(local_path, self.bucket, s3_key)
            self.logger.info(f"Uploaded {local_path} to s3://{self.bucket}/{s3_key}")
            return True
        except ClientError as e:
            self.logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """
        Download a file from S3
        
        Args:
            s3_key: S3 key (path in bucket)
            local_path: Where to save the file locally
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.s3.download_file(self.bucket, s3_key, local_path)
            self.logger.info(f"Downloaded s3://{self.bucket}/{s3_key} to {local_path}")
            return True
        except ClientError as e:
            self.logger.error(f"Failed to download {s3_key}: {e}")
            return False
    
    def list_objects(self, prefix: str = '', max_keys: int = 1000):
        """
        List objects in bucket with given prefix
        
        Args:
            prefix: S3 prefix to filter by (e.g., 'raw/papers/')
            max_keys: Maximum number of objects to return
        
        Returns:
            List of object keys
        """
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            self.logger.error(f"Failed to list objects: {e}")
            return []
    
    def delete_object(self, s3_key: str) -> bool:
        """Delete an object from S3"""
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=s3_key)
            self.logger.info(f"Deleted s3://{self.bucket}/{s3_key}")
            return True
        except ClientError as e:
            self.logger.error(f"Failed to delete {s3_key}: {e}")
            return False


# Usage example
if __name__ == "__main__":
    # Test the S3 client
    s3_client = S3Client()
    
    # List objects in raw/papers/
    papers = s3_client.list_objects(prefix='raw/papers/')
    print(f"Found {len(papers)} papers in S3")