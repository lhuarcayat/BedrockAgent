"""
Test refactored functions in classification module.
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the classification module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../functions/classification/src'))
# Add the shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../functions'))

class TestRefactoredFunctions(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        os.environ['REGION'] = 'us-east-1'
        os.environ['IDEMPOTENCY_TABLE'] = 'test-table'
        
    def test_calculate_processing_stats(self):
        """Test calculate_processing_stats function."""
        from index import calculate_processing_stats
        
        # Test data
        results = [
            {'status': 'success'},
            {'status': 'success'},
            {'status': 'skipped'},
            {'status': 'error'}
        ]
        failed_message_ids = ['msg1']
        total_messages = 4
        
        # Call function
        stats = calculate_processing_stats(results, failed_message_ids, total_messages)
        
        # Assertions
        self.assertEqual(stats['totalMessages'], 4)
        self.assertEqual(stats['successfulProcessing'], 2)
        self.assertEqual(stats['skippedLockNotAcquired'], 1)
        self.assertEqual(stats['failedProcessing'], 1)
        self.assertTrue(stats['exactlyOnceEffective'])
        
    def test_validate_s3_key_valid(self):
        """Test validate_s3_key with valid key."""
        from index import validate_s3_key
        
        valid_key = "par-servicios-poc/CERL/123456/document.pdf"
        is_valid, doc_number = validate_s3_key(valid_key)
        
        self.assertTrue(is_valid)
        self.assertEqual(doc_number, "123456")
        
    def test_validate_s3_key_invalid(self):
        """Test validate_s3_key with invalid key."""
        from index import validate_s3_key
        
        # Test non-PDF file
        invalid_key = "par-servicios-poc/CERL/123456/document.txt"
        is_valid, error = validate_s3_key(invalid_key)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "Not a PDF file")
        
        # Test no document number
        invalid_key2 = "par-servicios-poc/CERL/document.pdf"
        is_valid2, error2 = validate_s3_key(invalid_key2)
        
        self.assertFalse(is_valid2)
        self.assertEqual(error2, "No document number folder found in path")

    @patch('index.acquire_processing_lock')
    @patch('index.release_processing_lock')
    @patch('index.process_pdf')
    def test_process_single_s3_record_success(self, mock_process_pdf, mock_release_lock, mock_acquire_lock):
        """Test process_single_s3_record with successful processing."""
        from index import process_single_s3_record
        
        # Setup mocks
        mock_acquire_lock.return_value = (True, "Lock acquired")
        mock_process_pdf.return_value = {"test": "payload"}
        
        # Create mock clients
        s3_client = Mock()
        s3_client.get_object.return_value = {'Body': Mock(read=Mock(return_value=b'fake pdf content'))}
        dynamodb_client = Mock()
        
        # Test data
        s3_record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'par-servicios-poc/CERL/123456/document.pdf'}
            }
        }
        message_id = 'test-message-id'
        
        # Call function
        result, should_fail = process_single_s3_record(s3_record, message_id, s3_client, dynamodb_client)
        
        # Assertions
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['messageId'], message_id)
        self.assertEqual(result['key'], 'par-servicios-poc/CERL/123456/document.pdf')
        self.assertFalse(should_fail)
        
        # Verify mocks were called
        mock_acquire_lock.assert_called_once()
        mock_process_pdf.assert_called_once()
        mock_release_lock.assert_called_once()

if __name__ == '__main__':
    unittest.main()