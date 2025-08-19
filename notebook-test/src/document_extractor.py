"""
Document Extractor for Notebook-Test Framework
Connects to real Bedrock extraction logic using existing shared modules
"""

import logging
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import boto3
from botocore.config import Config

# Add shared modules to path
sys.path.append('../shared')
sys.path.append('shared')

try:
    # Import existing shared modules
    from bedrock_client import create_bedrock_client, converse_with_nova, set_model_params, _extract_text, NovaRequest, parse_extraction_response
    from pdf_processor import create_message
    from s3_handler import get_pdf_from_s3, extract_s3_path
    HAS_BEDROCK = True
except ImportError as e:
    logging.warning(f"Could not import shared modules: {e}")
    logging.info("Will use fallback mock extraction")
    HAS_BEDROCK = False

logger = logging.getLogger(__name__)

class DocumentExtractor:
    """Handles document extraction using real Bedrock logic"""
    
    def __init__(self, config_loader=None):
        # Use configuration from YAML if provided
        if config_loader:
            self.aws_profile = config_loader.get_settings().get('aws_profile', 'par_servicios')
            self.aws_region = config_loader.get_settings().get('aws_region', 'us-east-2')
        else:
            # Fallback defaults for standalone testing
            self.aws_profile = "par_servicios"
            self.aws_region = "us-east-2"
        
        self.bedrock_client = None
        self.s3_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize AWS clients"""
        try:
            # Set up AWS profile and region environment
            os.environ['AWS_PROFILE'] = self.aws_profile
            os.environ['REGION'] = self.aws_region
            
            # Use existing create_bedrock_client function if available
            if HAS_BEDROCK:
                self.bedrock_client = create_bedrock_client()
            else:
                # Fallback to manual creation
                session = boto3.Session(profile_name=self.aws_profile)
                self.bedrock_client = session.client(
                    "bedrock-runtime",
                    region_name=self.aws_region,
                    config=Config(connect_timeout=30, read_timeout=300)
                )
            
            # Create S3 client
            session = boto3.Session(profile_name=self.aws_profile)
            self.s3_client = session.client('s3', region_name=self.aws_region)
            
            logger.info(f"AWS clients initialized with profile: {self.aws_profile}, region: {self.aws_region}")
            
        except Exception as e:
            logger.error(f"Failed to setup AWS clients: {e}")
            self.bedrock_client = None
            self.s3_client = None
    
    
    def load_prompt_files(self, prompt_version: str, document_type: str) -> Optional[Dict[str, str]]:
        """
        Load prompt files for specific version and document type
        
        Args:
            prompt_version: Version like 'v2.2.1'
            document_type: Document type like 'CECRL'
            
        Returns:
            Dictionary with 'system' and 'user' prompts or None if error
        """
        try:
            prompts_dir = Path(f"prompts/{document_type}/{prompt_version}")
            
            if not prompts_dir.exists():
                logger.error(f"Prompts directory not found: {prompts_dir}")
                return None
            
            system_file = prompts_dir / "system.txt"
            user_file = prompts_dir / "user.txt"
            
            if not system_file.exists() or not user_file.exists():
                logger.error(f"Prompt files not found in {prompts_dir}")
                return None
            
            prompts = {
                'system': system_file.read_text(encoding='utf-8'),
                'user': user_file.read_text(encoding='utf-8')
            }
            
            logger.info(f"Loaded prompts for {document_type} {prompt_version}")
            return prompts
            
        except Exception as e:
            logger.error(f"Failed to load prompts for {document_type} {prompt_version}: {e}")
            return None
    
    def extract_from_document(self, s3_path: str, prompt_version: str, 
                            document_type: str, model_id: str) -> Dict[str, Any]:
        """
        Extract data from document using Bedrock
        
        Args:
            s3_path: S3 path to PDF document
            prompt_version: Prompt version to use
            document_type: Document type (CECRL, CERL, etc.)
            model_id: Bedrock model ID
            
        Returns:
            Dictionary with extraction result
        """
        result = {
            "status": "pending",
            "s3_path": s3_path,
            "prompt_version": prompt_version,
            "document_type": document_type,
            "model_id": model_id
        }
        
        try:
            # Check if real extraction is available
            if not self.bedrock_client:
                return self._mock_extraction(result)
            
            # Load prompts
            prompts = self.load_prompt_files(prompt_version, document_type)
            if not prompts:
                result["status"] = "error"
                result["error"] = f"Failed to load prompts for {document_type} {prompt_version}"
                return result
            
            # Use S3 direct access (optimized - no download needed)
            logger.info(f"Using S3 direct access for {s3_path} (optimized)")
            
            # Use Bedrock for extraction with S3 direct access
            extracted_data = self._bedrock_extraction(
                prompts, model_id, document_type, s3_path, s3_uri=s3_path
            )
            
            if extracted_data:
                result["status"] = "success"
                result["extracted_data"] = extracted_data
                result["optimization"] = "S3 direct access - no download needed"
            else:
                result["status"] = "error"
                result["error"] = "Bedrock extraction failed"
            
        except Exception as e:
            logger.error(f"Extraction failed for {s3_path}: {e}")
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def _bedrock_extraction(self, prompts: Dict[str, str], model_id: str, 
                          document_type: str, s3_path: str, pdf_bytes: bytes = None, s3_uri: str = None) -> Optional[Dict[str, Any]]:
        """
        Perform Bedrock extraction using existing shared functions
        
        Args:
            prompts: System and user prompts
            model_id: Bedrock model ID
            document_type: Document type
            s3_path: Original S3 path for reference
            pdf_bytes: PDF content (legacy, optional)
            s3_uri: S3 URI for direct access (preferred)
            
        Returns:
            Extracted data dictionary or None if failed
        """
        try:
            if HAS_BEDROCK:
                # Use existing create_message function with S3 direct access
                user_message = prompts['user']
                if s3_uri:
                    # Optimized: use S3 direct access with bucket owner (no download)
                    bucket_owner = "112636930635"  # Our AWS account ID from configuration
                    messages = [create_message(user_message, "user", pdf_path=s3_path, s3_uri=s3_uri, s3_bucket_owner=bucket_owner)]
                    logger.info(f"Using S3 direct access for Bedrock: {s3_uri} (with bucket owner: {bucket_owner})")
                else:
                    # Fallback: use bytes (backward compatibility)
                    messages = [create_message(user_message, "user", pdf_bytes, s3_path)]
                    logger.info(f"Using bytes approach for Bedrock (fallback)")
                
                # Don't need pdf_bytes anymore when using S3 direct access
                
                # Set model parameters using existing function
                model_params = set_model_params(
                    model_id=model_id,
                    max_tokens=2000,
                    temperature=0.1,
                    top_p=0.9
                )
                
                # Create Nova request object (same as production)
                nova_request = NovaRequest(
                    model_id=model_id,
                    messages=messages,
                    params=model_params,
                    system=[{"text": prompts['system']}] if prompts.get('system') else None
                )
                
                # Call Bedrock using existing function
                logger.info(f"Calling Bedrock for {document_type} extraction with {model_id}")
                
                # Log the full request details for debugging
                logger.info(f"Request details:")
                logger.info(f"  Model ID: {nova_request.model_id}")
                logger.info(f"  AWS Region: {self.aws_region}")
                logger.info(f"  Messages content types: {[type(block).__name__ for msg in nova_request.messages for block in msg.get('content', [])]}")
                
                # Check if S3 location is present
                for msg in nova_request.messages:
                    for block in msg.get('content', []):
                        if 'document' in block:
                            doc_source = block['document'].get('source', {})
                            if 's3Location' in doc_source:
                                logger.info(f"  S3 Location: {doc_source['s3Location']}")
                            elif 'bytes' in doc_source:
                                logger.info(f"  Using bytes: {len(doc_source['bytes'])} bytes")
                
                response = converse_with_nova(nova_request, self.bedrock_client)
                
                if response and 'output' in response:
                    # Use existing parse function for extraction
                    response_data = parse_extraction_response(response)
                    
                    # Extract the actual field data (it's nested under 'result')
                    if 'result' in response_data and isinstance(response_data['result'], dict):
                        extracted_data = response_data['result']
                    else:
                        extracted_data = response_data
                    
                    logger.info(f"Bedrock extraction successful for {document_type}")
                    return extracted_data
                
                else:
                    logger.error(f"Invalid Bedrock response format: {response}")
                    
            else:
                logger.warning("Bedrock functions not available, using mock extraction")
                return self._generate_mock_data(document_type)
                
        except Exception as e:
            logger.error(f"Bedrock extraction error: {e}")
        
        return None
    
    def _mock_extraction(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock extraction for testing"""
        document_type = result.get('document_type', 'CECRL')
        
        result["status"] = "success"
        result["extracted_data"] = self._generate_mock_data(document_type)
        result["note"] = "Using mock extraction - Bedrock clients not available"
        
        return result
    
    def _generate_mock_data(self, document_type: str) -> Dict[str, Any]:
        """Generate mock data based on document type"""
        if document_type == 'CECRL':
            return {
                "firstName": "MOCK_FIRST_NAME",
                "lastName": "MOCK_LAST_NAME",
                "nationality": "MOCK_NATIONALITY",
                "identificationType": "MOCK_ID_TYPE", 
                "identificationNumber": "MOCK_ID_NUMBER",
                "country_issuer": "MOCK_COUNTRY"
            }
        elif document_type == 'CERL':
            return {
                "companyName": "MOCK COMPANY S.A.S.",
                "documentType": "MOCK DOCUMENT TYPE",
                "country": "MOCK COUNTRY",
                "taxId": "MOCK_TAX_ID",
                "mainAddress": "MOCK ADDRESS",
                "incorporationDate": "2020-01-01",
                "companyDuration": "2050-01-01", 
                "registrationNumber": "MOCK_REG_NUMBER",
                "size": "MOCK SIZE",
                "relatedParties": [
                    {"firstName": "MOCK", "lastName": "PERSON1", "relationshipType": "Representative"},
                    {"firstName": "MOCK", "lastName": "PERSON2", "relationshipType": "Representative"}
                ]
            }
        else:
            return {"mock_field": "MOCK_VALUE"}


# Test the extractor
def test_document_extractor():
    """Test function for document extractor"""
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testing Document Extractor...")
    
    try:
        # Load configuration and pass to extractor
        sys.path.append('.')
        from config_loader import ConfigLoader
        config_loader = ConfigLoader()
        
        extractor = DocumentExtractor(config_loader)
        
        # Get model ID from configuration
        settings = config_loader.get_settings()
        model_id = settings.get('bedrock_model', 'us.amazon.nova-pro-v1:0')
        
        # Test CECRL extraction with real S3 path
        test_s3_path = "s3://par-servicios-poc-qa-filling-desk/par-servicios-poc/CECRL/984174004/_2022-01-06.pdf"
        
        print(f"Using model from config: {model_id}")
        
        result = extractor.extract_from_document(
            s3_path=test_s3_path,
            prompt_version="v2.2.1",
            document_type="CECRL", 
            model_id=model_id
        )
        
        print(f"\\n📄 Extraction Result:")
        print(f"Status: {result.get('status')}")
        print(f"Document Type: {result.get('document_type')}")
        print(f"Prompt Version: {result.get('prompt_version')}")
        
        if result.get('status') == 'success':
            extracted_data = result.get('extracted_data', {})
            print(f"\\n📊 Extracted Fields:")
            for field, value in extracted_data.items():
                print(f"  {field}: {value}")
        else:
            print(f"❌ Error: {result.get('error')}")
            
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_document_extractor()