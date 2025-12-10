"""
M1: Infrastructure Setup Tests
Tests for AWS S3, environment configuration
"""

import pytest
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

load_dotenv()


class TestEnvironmentSetup:
    """Test environment variables and configuration"""

    def test_env_variables_exist(self):
        """Test that all required environment variables are set"""
        print("\n🧪 Testing environment variables...")

        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
            "S3_BUCKET_NAME",
        ]

        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)

        assert len(missing) == 0, f"Missing environment variables: {missing}"
        print(f"   ✅ All {len(required_vars)} required variables set")

    def test_aws_credentials_valid(self):
        """Test that AWS credentials are valid"""
        print("\n🧪 Testing AWS credentials...")

        try:
            s3 = boto3.client("s3")
            s3.list_buckets()
            print("   ✅ AWS credentials are valid")
        except (ClientError, NoCredentialsError) as e:
            pytest.fail(f"Invalid AWS credentials: {e}")


class TestS3Infrastructure:
    """Test S3 bucket setup"""

    def test_bucket_exists(self):
        """Test that project bucket exists"""
        print("\n🧪 Testing S3 bucket existence...")

        bucket_name = os.getenv("S3_BUCKET_NAME")
        s3 = boto3.client("s3")

        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"   ✅ Bucket exists: {bucket_name}")
        except (ClientError, NoCredentialsError) as e:
            error_code = (
                e.response.get("Error", {}).get("Code")
                if isinstance(e, ClientError)
                else None
            )
            if isinstance(e, NoCredentialsError):
                pytest.fail(f"AWS credentials not available: {e}")
            elif error_code == "404":
                pytest.fail(f"Bucket does not exist: {bucket_name}")
            else:
                pytest.fail(f"Error accessing bucket: {e}")

    def test_bucket_has_folders(self):
        """Test that bucket has correct folder structure"""
        print("\n🧪 Testing bucket folder structure...")

        bucket_name = os.getenv("S3_BUCKET_NAME")
        s3 = boto3.client("s3")

        expected_folders = ["raw/", "processed/", "embeddings/", "reports/"]

        try:
            response = s3.list_objects_v2(Bucket=bucket_name, Delimiter="/")
        except (ClientError, NoCredentialsError) as e:
            if isinstance(e, NoCredentialsError):
                pytest.fail(f"AWS credentials not available: {e}")
            raise

        if "CommonPrefixes" in response:
            folders = [p["Prefix"] for p in response["CommonPrefixes"]]

            for expected in expected_folders:
                assert expected in folders, f"Missing folder: {expected}"

            print(f"   ✅ Found {len(folders)} folders")
        else:
            pytest.fail("No folders found in bucket")

    def test_write_permission(self):
        """Test that we have write permission to bucket"""
        print("\n🧪 Testing S3 write permissions...")

        bucket_name = os.getenv("S3_BUCKET_NAME")
        s3 = boto3.client("s3")

        test_key = "test/.write_test.txt"

        try:
            # Try to write
            s3.put_object(Bucket=bucket_name, Key=test_key, Body=b"test")

            # Clean up
            s3.delete_object(Bucket=bucket_name, Key=test_key)

            print("   ✅ Write permissions confirmed")
        except (ClientError, NoCredentialsError) as e:
            if isinstance(e, NoCredentialsError):
                pytest.fail(f"AWS credentials not available: {e}")
            pytest.fail(f"No write permission: {e}")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
