"""
S3 Bucket Setup Script for aiRA Research Assistant
"""

import boto3
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

def setup_s3_bucket():
    """Create S3 bucket and folder structure"""
    
    # Get from environment
    BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    REGION = os.getenv('AWS_REGION', 'us-east-1')
    
    if not BUCKET_NAME:
        print("❌ Error: S3_BUCKET_NAME not set in .env file")
        sys.exit(1)
    
    print(f"🚀 Setting up S3 bucket: {BUCKET_NAME}")
    print(f"📍 Region: {REGION}\n")
    
    try:
        s3 = boto3.client('s3', region_name=REGION)
    except Exception as e:
        print(f"❌ Error connecting to AWS: {e}")
        print("💡 Run: aws configure")
        sys.exit(1)
    
    # Create bucket
    try:
        if REGION == 'us-east-1':
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={'LocationConstraint': REGION}
            )
        print(f"✅ Created bucket: {BUCKET_NAME}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"ℹ️  Bucket already exists: {BUCKET_NAME}")
    except s3.exceptions.BucketAlreadyExists:
        print(f"❌ Bucket name taken. Try another name in .env")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error creating bucket: {e}")
        sys.exit(1)
    
    # Create folder structure
    folders = [
        'raw/web/',
        'raw/papers/',
        'processed/text_chunks/',
        'processed/tables/',
        'processed/ocr/',
        'embeddings/',
        'reports/'
    ]
    
    print("\n📁 Creating folder structure:")
    for folder in folders:
        try:
            s3.put_object(Bucket=BUCKET_NAME, Key=folder)
            print(f"  ✅ {folder}")
        except Exception as e:
            print(f"  ❌ Error creating {folder}: {e}")
    
    print("\n🎉 S3 setup complete!")
    print(f"\n📊 View your bucket:")
    print(f"   https://s3.console.aws.amazon.com/s3/buckets/{BUCKET_NAME}")
    
    return True

if __name__ == "__main__":
    setup_s3_bucket()