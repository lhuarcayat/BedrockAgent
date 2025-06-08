import json
import base64
import os
import sys
from index import handler

def read_pdf_file(file_path):
    """Read a PDF file and return its content as bytes."""
    with open(file_path, 'rb') as file:
        return file.read()

def test_lambda_handler():
    """Test the Lambda handler function with a sample PDF."""
    # Path to a sample PDF file
    # You may need to adjust this path to point to an actual PDF file in your project
    pdf_path = "../files_examples/800035887/9_CamCom_2020-02-28.pdf"

    if not os.path.exists(pdf_path):
        print(f"PDF file not found at {pdf_path}")
        print("Please adjust the path to point to an actual PDF file")
        return

    # Read the PDF file
    pdf_content = read_pdf_file(pdf_path)

    # Create a test event
    event = {
        'pdf_content': base64.b64encode(pdf_content).decode('utf-8'),
        'folder_path': "CERL/800035887/9_CamCom_2020-02-28.pdf"
    }

    # Call the handler function
    print("Testing classification Lambda with sample PDF...")
    response = handler(event, None)

    # Print the response
    print("\nLambda Response:")
    print(f"Status code: {response['statusCode']}")
    print(f"Body: {json.dumps(json.loads(response['body']), indent=2)}")

    print("\nTest completed. Check the logs above to verify the Lambda processed the PDF correctly.")

    return response

if __name__ == "__main__":
    test_lambda_handler()
