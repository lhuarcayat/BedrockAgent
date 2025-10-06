"""
DynamoDB-based idempotency handler for exactly-once processing.

This module provides atomic locking mechanisms using DynamoDB conditional writes
to ensure that files are processed exactly once, even with SQS at-least-once delivery.

Key features:
- Atomic lock acquisition using DynamoDB conditional PutItem
- Automatic file version handling via S3 versionId
- Cross-system protection (works across Lambda functions)
- Automatic cleanup via TTL
- Resilient error handling
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .s3_handler import extract_s3_path

logger = logging.getLogger(__name__)

def acquire_processing_lock(dynamodb_client, folder_path, s3_client):
    """
    DynamoDB-based exactly-once processing safeguard using atomic conditional PutItem.
    
    This implementation ensures exactly-once processing by using DynamoDB's conditional
    write operations. Only one Lambda can successfully acquire the lock for a given
    (bucket, key, versionId) combination.
    
    The lock key includes S3 versionId to naturally handle file updates:
    - Same file (same versionId): Lock exists Skip processing
    - Updated file (new versionId): New lock key Allow processing
    
    Args:
        dynamodb_client: boto3 DynamoDB client
        folder_path: Original S3 path (s3://bucket/key)
        s3_client: boto3 S3 client (for getting object version)
        
    Returns:
        tuple(bool, str): (lock_acquired, reason)
        - lock_acquired: True if this Lambda acquired the lock (proceed with processing)
        - reason: Human-readable reason (for logging)
    """
    try:
        # Extract S3 object information
        source_bucket, source_key = extract_s3_path(folder_path)
        
        # Get S3 object version for true idempotency
        version_id = _get_s3_object_version(s3_client, source_bucket, source_key, folder_path)
        
        # Create composite primary key: bucket#key#versionId
        # This ensures that file updates (new versions) get processed
        primary_key = f"{source_bucket}#{source_key}#{version_id}"
        
        # Calculate TTL (30 days from now for cleanup)
        ttl_timestamp = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        
        table_name = os.environ.get('IDEMPOTENCY_TABLE')
        if not table_name:
            logger.warning("IDEMPOTENCY_TABLE not configured, skipping atomic locking")
            return True, "DynamoDB not configured - proceeding without lock"
        
        # Attempt atomic lock acquisition using conditional PutItem
        try:
            dynamodb_client.put_item(
                TableName=table_name,
                Item={
                    'pk': {'S': primary_key},
                    'status': {'S': 'PROCESSING'},
                    'folder_path': {'S': folder_path},
                    'bucket': {'S': source_bucket},
                    'key': {'S': source_key},
                    'version_id': {'S': version_id},
                    'acquired_at': {'S': datetime.now(timezone.utc).isoformat()},
                    'expires_at': {'N': str(ttl_timestamp)}
                },
                ConditionExpression='attribute_not_exists(pk)'
            )
            
            # Success! This Lambda won the race and acquired the lock
            logger.info(f"Successfully acquired processing lock for {folder_path} (key: {primary_key})")
            return True, "Lock acquired successfully"
            
        except dynamodb_client.exceptions.ConditionalCheckFailedException:
            # Another Lambda already acquired the lock for this file version
            logger.info(f"Processing lock already exists for {folder_path} (key: {primary_key})")
            
            # Optional: Check existing lock details for debugging
            lock_details = _get_existing_lock_details(dynamodb_client, table_name, primary_key)
            return False, f"Already being processed ({lock_details})"
        
    except Exception as e:
        logger.error(f"Error in DynamoDB lock acquisition: {str(e)}")
        # On error, err on the side of processing to avoid blocking valid requests
        return True, f"Error acquiring lock - proceeding anyway: {str(e)}"

def release_processing_lock(dynamodb_client, folder_path, s3_client, success=True):
    """
    Release the DynamoDB processing lock and update status.
    
    This function updates the lock status to DONE or FAILED and adds completion timestamp.
    The lock will be automatically cleaned up by DynamoDB TTL after 30 days.
    
    Args:
        dynamodb_client: boto3 DynamoDB client
        folder_path: Original S3 path (s3://bucket/key)
        s3_client: boto3 S3 client
        success: Whether processing was successful
    """
    try:
        # Reconstruct the same primary key used in acquire_processing_lock
        source_bucket, source_key = extract_s3_path(folder_path)
        version_id = _get_s3_object_version(s3_client, source_bucket, source_key, folder_path)
        primary_key = f"{source_bucket}#{source_key}#{version_id}"
        
        table_name = os.environ.get('IDEMPOTENCY_TABLE')
        if not table_name:
            logger.debug("IDEMPOTENCY_TABLE not configured, skipping lock release")
            return
        
        # Update status to DONE (or FAILED)
        status = 'DONE' if success else 'FAILED'
        update_expression = 'SET #status = :status, completed_at = :completed_at'
        
        dynamodb_client.update_item(
            TableName=table_name,
            Key={'pk': {'S': primary_key}},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': {'S': status},
                ':completed_at': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        
        logger.debug(f"Released processing lock for {folder_path} with status: {status}")
        
    except Exception as e:
        logger.warning(f"Error releasing processing lock: {str(e)}")
        # Non-critical error - don't fail the entire process

def _get_s3_object_version(s3_client, source_bucket, source_key, folder_path):
    """
    Get S3 object version ID for idempotency key construction.
    
    Args:
        s3_client: boto3 S3 client
        source_bucket: S3 bucket name
        source_key: S3 object key
        folder_path: Original S3 path (for logging)
        
    Returns:
        str: Version ID or fallback identifier
    """
    try:
        head_response = s3_client.head_object(Bucket=source_bucket, Key=source_key)
        version_id = head_response.get('VersionId', 'null')
        etag = head_response.get('ETag', '').strip('"')
        logger.debug(f"S3 object metadata: VersionId={version_id}, ETag={etag}")
        return version_id
    except Exception as e:
        logger.warning(f"Could not get S3 object version for {folder_path}: {str(e)}")
        # Use timestamp as fallback to ensure some uniqueness
        return f"unknown_{int(datetime.now(timezone.utc).timestamp())}"

def _get_existing_lock_details(dynamodb_client, table_name, primary_key):
    """
    Get details about existing lock for debugging purposes.
    
    Args:
        dynamodb_client: boto3 DynamoDB client
        table_name: DynamoDB table name
        primary_key: Lock primary key
        
    Returns:
        str: Human-readable lock details
    """
    try:
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={'pk': {'S': primary_key}}
        )
        if 'Item' in response:
            item = response['Item']
            status = item.get('status', {}).get('S', 'unknown')
            acquired_at = item.get('acquired_at', {}).get('S', 'unknown')
            return f"status: {status}, acquired at: {acquired_at}"
        else:
            return "lock details not found"
    except Exception as e:
        logger.debug(f"Could not check existing lock details: {str(e)}")
        return "unable to get lock details"

