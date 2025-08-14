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
    region = region or os.environ.get('REGION', 'us-east-1')
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
    region = region or os.environ.get('REGION', 'us-east-1')
    try:
        client = boto3.client('dynamodb', region_name=region)
        logger.debug(f"Created DynamoDB client for region: {region}")
        return client
    except Exception as e:
        logger.error(f"Failed to create DynamoDB client: {str(e)}")
        raise

def create_sqs_client(region=None):
    """
    Create an SQS client with the appropriate region.
    
    Args:
        region: AWS region (defaults to REGION environment variable)
        
    Returns:
        boto3.client: SQS client
    """
    region = region or os.environ.get('REGION', 'us-east-1')
    try:
        client = boto3.client('sqs', region_name=region)
        logger.debug(f"Created SQS client for region: {region}")
        return client
    except Exception as e:
        logger.error(f"Failed to create SQS client: {str(e)}")
        raise

def create_bedrock_client(region=None):
    """
    Create a Bedrock client with the appropriate region.
    
    Args:
        region: AWS region (defaults to REGION environment variable)
        
    Returns:
        boto3.client: Bedrock Runtime client
    """
    region = region or os.environ.get('REGION', 'us-east-1')
    try:
        client = boto3.client('bedrock-runtime', region_name=region)
        logger.debug(f"Created Bedrock client for region: {region}")
        return client
    except Exception as e:
        logger.error(f"Failed to create Bedrock client: {str(e)}")
        raise

def get_all_clients(region=None):
    """
    Create all commonly used AWS clients.
    
    Args:
        region: AWS region (defaults to REGION environment variable)
        
    Returns:
        dict: Dictionary of AWS clients
    """
    region = region or os.environ.get('REGION', 'us-east-1')
    
    return {
        's3': create_s3_client(region),
        'dynamodb': create_dynamodb_client(region),
        'sqs': create_sqs_client(region),
        'bedrock': create_bedrock_client(region)
    }