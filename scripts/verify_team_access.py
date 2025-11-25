"""
Verify that a team member has correct AWS S3 access
Run this after setting up your .env file
"""

import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

def verify_access():
    """Verify AWS S3 access is configured correctly"""
    
    print("🔍 Verifying AWS S3 Access for aiRA Project\n")
    print("="*60)
    
    # Check environment variables
    print("\n1️⃣ Checking Environment Variables:")
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION')
    bucket = os.getenv('S3_BUCKET_NAME')
    
    checks = {
        'AWS_ACCESS_KEY_ID': access_key,
        'AWS_SECRET_ACCESS_KEY': secret_key,
        'AWS_REGION': region,
        'S3_BUCKET_NAME': bucket
    }
    
    missing = []
    for key, value in checks.items():
        if value:
            if 'KEY' in key or 'SECRET' in key:
                display = value[:8] + '*' * 10
            else:
                display = value
            print(f"   ✅ {key}: {display}")
        else:
            print(f"   ❌ {key}: NOT SET")
            missing.append(key)
    
    if missing:
        print(f"\n❌ Missing variables: {', '.join(missing)}")
        print("💡 Add these to your .env file")
        return False
    
    # Test S3 connection
    print("\n2️⃣ Testing S3 Connection:")
    try:
        s3 = boto3.client('s3', region_name=region)
        response = s3.list_buckets()
        print(f"   ✅ Connected to AWS S3")
        print(f"   📊 You can see {len(response['Buckets'])} bucket(s)")
    except ClientError as e:
        print(f"   ❌ Connection failed: {e}")
        return False
    
    # Test project bucket access
    print("\n3️⃣ Testing Project Bucket Access:")
    try:
        # Try to list objects (even if empty)
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        print(f"   ✅ You have READ access to '{bucket}'")
        
        # Try to put a test object
        test_key = 'test/.team_access_test.txt'
        s3.put_object(
            Bucket=bucket, 
            Key=test_key, 
            Body=b'Team access test'
        )
        print(f"   ✅ You have WRITE access to '{bucket}'")
        
        # Clean up test object
        s3.delete_object(Bucket=bucket, Key=test_key)
        print(f"   ✅ You have DELETE access to '{bucket}'")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            print(f"   ❌ Bucket '{bucket}' does not exist")
            print(f"   💡 Ask Natnicha to run: python scripts/setup_s3.py")
        elif error_code == 'AccessDenied':
            print(f"   ❌ Access denied to '{bucket}'")
            print(f"   💡 Ask Natnicha to verify you're in the IAM user group")
        else:
            print(f"   ❌ Error: {e}")
        return False
    
    # Check folder structure
    print("\n4️⃣ Checking Bucket Structure:")
    try:
        response = s3.list_objects_v2(Bucket=bucket, Delimiter='/')
        if 'CommonPrefixes' in response:
            folders = [p['Prefix'] for p in response['CommonPrefixes']]
            print(f"   ✅ Found {len(folders)} folders:")
            for folder in sorted(folders):
                print(f"      • {folder}")
        else:
            print(f"   ⚠️  No folders found (bucket might be empty)")
            print(f"   💡 Run: python scripts/setup_s3.py")
    except Exception as e:
        print(f"   ⚠️  Could not list folders: {e}")
    
    print("\n" + "="*60)
    print("🎉 All checks passed! You're ready to work on the project.")
    print("\n📝 Next steps:")
    print("   1. Test fetching papers: python scripts/test_arxiv_fetch.py")
    print("   2. Start working on your assigned milestone")
    print("   3. Remember: Never commit your .env file!")
    
    return True

if __name__ == "__main__":
    verify_access()