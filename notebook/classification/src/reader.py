import boto3
import json
import os
import sys
import base64

# from shared.helper import *
from pathlib import Path

# region = os.environ.get['AWS_REGION']
# bedrock_runtime = boto3.client(
#     service_name='bedrock-runtime',
#     region_name=region
# )


def read_document_data(image_path: Path):
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    return b64


def create_client(service_name, region):
    client = boto3.client(
        service_name=service_name,
        region_name=region
    )
    return client


def get_instructions(action):
    instruction_files = {
        'clasification': './instructions/clasification.txt',
    }
    default_file = '.instructions/clasification.txt'

    file_path = instruction_files.get(action, default_file)
    with open(file_path, 'r') as file:
        return file.read()


def read_document(file_to_read):
    with open(file_to_read, "rb") as document:
        raw = document.read()
        return raw


def create_messages(prompt: str, pdf_bytes: bytes):
    # One single message that contains both:
    #  1) A text prompt block to tell the model what to do, and
    #  2) A document block carrying your PDF
    msg = {
        "role": "user",
        "content": [
            # 1) prompt about what you want done
            {"text": prompt},

            # 2) the PDF itself, under a "document" key:
            {
                "document": {
                    "name":   "document_to_evaluate.pdf",  # an arbitrary label
                    "format": "pdf",                       # file format
                    "source": {
                        "bytes": pdf_bytes                # raw bytes → SDK handles the rest
                    }
                }
            }
        ]
    }
    return [msg]

def create_messages_for_claude(prompt: str, pdf_bytes: bytes):
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "document",
                    "document": {
                        "name": "document_to_evaluate.pdf",
                        "format": "pdf",
                        "source": {
                            "bytes": pdf_bytes
                        }
                    }
                }
            ]
        }
    ]


# def create_messages(prompt, file_to_read):

#     system_message = {
#         "role": "system",
#         "content": prompt
#     }

#     user_message = {
#         "role": "user",
#         "content": [
#             {
#                 "format": "pdf",
#                 "name": "document_to_evaluate.pdf",
#                 "source": {
#                     "bytes": file_to_read
#                 }
#             }
#         ]
#     }
#     return [system_message, user_message]


def set_model_params(max_tokens=300, top_p=0.1, temperature=0.3):
    params = {
        "maxTokens": max_tokens,
        "topP": top_p,
        "temperature": temperature
    }
    return params

def set_claude_params(max_tokens=300, top_p=0.1, temperature=0.3):
    params = {
        "max_tokens": max_tokens,
        "top_p": top_p,
        "temperature": temperature
    }
    return params


def get_model_response(client, model_id, messages, params):
    # response = client.converse(
    #     modelId=model_id,
    #     messages=messages,
    #     inferenceConfig=params
    # )

    payload = {
        "messages": messages,
        "inferenceConfig": params
    }

    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        trace='ENABLED',
        body=json.dumps(payload).encode("utf-8")
    )

    body = response["body"].read().decode("utf-8")

    return json.loads(body)

def get_claude_response(client, model_id, messages, params):
    # response = client.converse(
    #     modelId=model_id,
    #     messages=messages,
    #     inferenceConfig=params
    # )

    payload = {
        "messages": messages,
        "inferenceConfig": params
    }

    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload).encode("utf-8"),
        trace='ENABLED'
    )

    body = response["body"].read().decode("utf-8")

    return json.loads(body)



def save_to_json(response, output_path="response_indented.json", indent=2):
    """
    Dumps `response` to JSON at `output_path`.
    If necessary, creates parent directories.
    Catches and reports serialization errors.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        with out.open("w", encoding="utf-8") as f:
            json.dump(response, f, indent=indent, ensure_ascii=False)
        print(f"✅ Saved JSON to {out}")
    except TypeError as e:
        print(f"⚠️ Could not JSON-serialize response: {e}")
        # Fall back to writing the raw repr
        with out.open("w", encoding="utf-8") as f:
            f.write(repr(response))
        print(f"🔧 Wrote raw Python repr to {out}")


def main():
    region = "us-east-1"
    # modelId = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    modelId = "us.amazon.nova-pro-v1:0"
    temperature = 0.1
    top_p = 0.9
    max_tokens = 8192

    client = create_client("bedrock-runtime", region)

    file_path = Path("../files_examples/800035887/9_CamCom_2020-02-28.pdf")
    file_to_read = read_document_data(file_path)

    clasification_prompt = get_instructions("clasification")

    messages = create_messages(clasification_prompt, file_to_read)

    params = set_model_params(max_tokens, top_p, temperature)

    model_response = get_model_response(client, modelId, messages, params)
    save_to_json(model_response, "outputs/my_result.json", 2)
    print(json.dumps(model_response, indent=2))


if __name__ == "__main__":
    main()
