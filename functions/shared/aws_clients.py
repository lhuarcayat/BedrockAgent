"""
AWS client factory utilities for consistent client creation across Lambda functions.

This module provides centralized AWS client creation with proper configuration
and error handling. It ensures consistent region and credential management.
"""

import os
import boto3
import logging

logger = logging.getLogger(__name__)

def create_s3_client(region=None):
    """
    Create an S3 client with the appropriate region.
    
    Args:
        region: AWS region (defaults to REGION environment variable)
        
    Returns:
        boto3.client: S3 client
    """
    region = region or os.environ.get('REGION', 'us-east-2')
    try:
        client = boto3.client('s3', region_name=region)
        logger.debug(f"Created S3 client for region: {region}")
        return client
    except Exception as e:
        logger.error(f"Failed to create S3 client: {str(e)}")
        raise

def create_dynamodb_client(region=None):
    """
    Create a DynamoDB client with the appropriate region.
    
    Args:
        region: AWS region (defaults to REGION environment variable)
        
    Returns:
        boto3.client: DynamoDB client
    """
    region = region or os.environ.get('REGION', 'us-east-2')
    try:
        client = boto3.client('dynamodb', region_name=region)
        logger.debug(f"Created DynamoDB client for region: {region}")
        return client
    except Exception as e:
        logger.error(f"Failed to create DynamoDB client: {str(e)}")
        raise