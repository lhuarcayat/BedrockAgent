# Classification Lambda package initialization
import boto3
import json
import os
import sys

from shared.helper import *
from pathlib import Path

region = os.environ.get['AWS_REGION']
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name=region
)

modelId = "amazon.nova-pro-v1:0"

# def lambda_handler(event, context):
#     prompt = "Classify the following text into one of the following categories: 'positive', 'negative', or 'neutral'.\n\nText: "
#     body = json.loads(event['body'])
#     text = body['text']
#     prompt += text
#     body = json.dumps({
#         "prompt": prompt,
#         "max_tokens_to_sample": 30,
#         "temperature": 0,
#         "top_p": 0.5,
#         "top_k": 50,
#         "stop_sequences": ["\n\nHuman:"],
#         "anthropic_version": "bedrock-2023-05-31"
#     })
#     response = bedrock_runtime.invoke_model(
#         body=body,
#         modelId="anthropic.claude-v2"
#     )
#     response_body = json.loads(response.get('body').read())
#     output_text = response_body.get('completion')
#     return {
#         'statusCode': 200,
#         'body': json.dumps({
#             'output': output_text
#         })
#     }

def get_instruction(lesson):
    instruction_files = {
        'clasification': './instructions/clasification.txt',
    }
    default_file = '.instructions/clasification.txt'

    file_path = instruction_files.get(lesson, default_file)
    with open(file_path, 'r') as file:
        return file.read()

def create_bedrock_agent(bedrock_agent, instruction, role_arn):
    response = bedrock_agent.create_agent(
        agentName='mugs-customer-support-agent',
        foundationModel='anthropic.claude-3-haiku-20240307-v1:0',
        instruction=instruction,
        agentResourceRoleArn=role_arn,
    )
    return response['agent']['agentId']

def main():
    lesson = sys.argv[1] if len(sys.argv) > 1 else None
    role_arn = os.environ['BEDROCKAGENTROLE']
    region_name = 'us-west-2'

    bedrock_agent = boto3.client(service_name='bedrock-agent', region_name=region_name)
    lambda_client = boto3.client('lambda', region_name=region_name)

    instruction = get_instruction(lesson)

    # Create and prepare the Bedrock Agent
    agent_id = create_bedrock_agent(bedrock_agent, instruction, role_arn)
    # print(f"agentId: {agent_id}")

    wait_for_agent_status(agentId=agent_id, targetStatus='NOT_PREPARED')
    bedrock_agent.prepare_agent(agentId=agent_id)
    wait_for_agent_status(agentId=agent_id, targetStatus='PREPARED')

    # Create an alias for the agent
    alias_response = bedrock_agent.create_agent_alias(
        agentAliasName='MyAgentAlias',
        agentId=agent_id
    )
    agent_alias_id = alias_response['agentAlias']['agentAliasId']
    # print(f"agentId: {agent_id}, agentAliasId: {agent_alias_id}")

    wait_for_agent_alias_status(agentId=agent_id, agentAliasId=agent_alias_id, targetStatus='PREPARED')

    # Set environment variables
    os.environ['BEDROCK_AGENT_ID'] = agent_id
    os.environ['BEDROCK_AGENT_ALIAS_ID'] = agent_alias_id

    # Create Lambda function
    random_suffix = get_random_suffix()
    # lambda_role_arn = create_lambda_iam_role(randomSuffix=random_suffix)
    lambda_role_arn = os.environ['LAMBDAEXECUTIONROLE']

    # print(f"Lambda IAM Role: {lambda_role_arn[:13]}{'*' * 12}{lambda_role_arn[25:]}")

    function_name = f"dlai-support-agent-{random_suffix}"
    function_arn = create_lambda_function(lambda_client, function_name, lambda_role_arn, lesson)

    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='AllowBedrockInvoke',
        Action='lambda:InvokeFunction',
        Principal='bedrock.amazonaws.com',
        SourceArn=f'arn:aws:bedrock:{region_name}:{boto3.client("sts").get_caller_identity()["Account"]}:agent/{agent_id}'
    )

    # print(f"Lambda function {function_name} created successfully.")

    os.environ['LAMBDA_FUNCTION_NAME'] = function_name
    os.environ['LAMBDA_FUNCTION_ARN'] = function_arn

if __name__ == "__main__":
    main()