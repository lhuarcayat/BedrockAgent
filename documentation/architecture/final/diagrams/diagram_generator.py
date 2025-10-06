#!/usr/bin/env python3
"""
AWS Architecture Diagram Generator for Par Servicios Document Processing System

This script generates AWS architecture diagrams for the Par Servicios document processing system
using the diagrams package. It creates both high-level and detailed architecture diagrams
based on the documentation in documento_tecnico.md and terraform/main.tf.
"""

import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.storage import S3
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SQS, SNS
from diagrams.aws.database import Dynamodb
from diagrams.aws.management import Cloudwatch
from diagrams.aws.security import IAM
from diagrams.aws.ml import Bedrock

# Create output directory if it doesn't exist
os.makedirs("documentation/V2/generated_diagrams", exist_ok=True)

# Define color mapping based on documentation
COLOR_MAPPING = {
    "S3": "#3F8624",
    "Lambda": "#F58536",
    "SQS": "#CC2264",
    "SNS": "#CC2264",
    "Model": "#3B48CC",
    "CloudWatch": "#3B48CC",
    "IAM": "#D86613"
}

def generate_high_level_diagram():
    """Generate the high-level architecture diagram."""
    with Diagram(
        "Par Servicios Document Processing Architecture",
        filename="documentation/architecture/v2/generated_diagrams/high_level_architecture",
        show=False,
        outformat=["png", "svg"],
        graph_attr={
            "bgcolor": "white",
            "pad": "0.5",
            "splines": "ortho",
            "nodesep": "1.5",
            "ranksep": "2.0",
            "fontsize": "16"
        }
    ):
        with Cluster("AWS Cloud"):
            # Classification Phase
            with Cluster("Classification Phase"):
                s3_filing_desk = S3("Document Filing Desk", fontcolor="black", color=COLOR_MAPPING["S3"])
                lambda_classification = Lambda("Classification Lambda", fontcolor="black", color=COLOR_MAPPING["Lambda"])
                model_check = Bedrock("Amazon Bedrock\nDocument Verification", fontcolor="black", color=COLOR_MAPPING["Model"])

                s3_filing_desk >> Edge(label="ObjectCreated event") >> lambda_classification
                lambda_classification - model_check

            # SQS Extraction Queue
            sqs_extraction = SQS("Extraction Queue", fontcolor="black", color=COLOR_MAPPING["SQS"])

            # DynamoDB Tables
            dynamodb_idempotency = Dynamodb("Idempotency Table", fontcolor="black", color=COLOR_MAPPING["Model"])
            dynamodb_manual_review = Dynamodb("Manual Review Table", fontcolor="black", color=COLOR_MAPPING["Model"])

            # Connect Classification Phase to SQS and Idempotency Table
            lambda_classification >> Edge(label="Valid Documents") >> sqs_extraction
            lambda_classification >> Edge(label="Deduplication") >> dynamodb_idempotency

            # Extraction Phase
            with Cluster("Extraction and Scoring Phase"):
                lambda_extraction = Lambda("Extraction & Scoring Lambda", fontcolor="black", color=COLOR_MAPPING["Lambda"])
                model_extract = Bedrock("Amazon Bedrock\nInformation Extraction", fontcolor="black", color=COLOR_MAPPING["Model"])

                sqs_extraction >> lambda_extraction
                lambda_extraction - model_extract

            # S3 Results
            s3_results = S3("JSON Results Bucket", fontcolor="black", color=COLOR_MAPPING["S3"])

            # SQS Fallback Queue
            sqs_fallback = SQS("Fallback Queue", fontcolor="black", color=COLOR_MAPPING["SQS"])

            # Connect Extraction Phase to outputs
            lambda_extraction >> Edge(label="High Score") >> s3_results
            lambda_extraction >> Edge(label="Low Score") >> sqs_fallback

            # Fallback Phase
            with Cluster("Fallback Phase"):
                lambda_fallback = Lambda("Fallback Processing Lambda", fontcolor="black", color=COLOR_MAPPING["Lambda"])
                model_fallback = Bedrock("Amazon Bedrock\nFallback Model", fontcolor="black", color=COLOR_MAPPING["Model"])

                sqs_fallback >> lambda_fallback
                lambda_fallback - model_fallback

            # Connect Fallback Phase to outputs and Manual Review Table
            lambda_fallback >> Edge(label="High Score") >> s3_results
            lambda_fallback >> Edge(label="Register for Manual Review") >> dynamodb_manual_review

            # Legend
            cloudwatch = Cloudwatch("CloudWatch", fontcolor="black", color=COLOR_MAPPING["CloudWatch"])
            iam_role = IAM("IAM Role", fontcolor="black", color=COLOR_MAPPING["IAM"])

def generate_detailed_diagram():
    """Generate the detailed architecture diagram with environment-specific resources."""
    with Diagram(
        "Par Servicios Detailed Architecture",
        filename="documentation/architecture/v2/generated_diagrams/detailed_architecture",
        show=False,
        outformat=["png", "svg"],
        graph_attr={
            "bgcolor": "white",
            "pad": "0.5",
            "splines": "ortho",
            "nodesep": "1.5",
            "ranksep": "2.0",
            "fontsize": "16"
        }
    ):
        with Cluster("AWS Cloud"):
            # S3 Buckets
            with Cluster("S3 Buckets"):
                filing_desk_dev = S3("Document Filing Desk (DEV)", fontcolor="black", color=COLOR_MAPPING["S3"])
                filing_desk_qa = S3("Document Filing Desk (QA)", fontcolor="black", color=COLOR_MAPPING["S3"])
                results_dev = S3("JSON Results Bucket (DEV)", fontcolor="black", color=COLOR_MAPPING["S3"])
                results_qa = S3("JSON Results Bucket (QA)", fontcolor="black", color=COLOR_MAPPING["S3"])

            # Lambda Functions
            with Cluster("Lambda Functions"):
                classification_dev = Lambda("Classification Lambda (DEV)", fontcolor="black", color=COLOR_MAPPING["Lambda"])
                classification_qa = Lambda("Classification Lambda (QA)", fontcolor="black", color=COLOR_MAPPING["Lambda"])
                extraction_dev = Lambda("Extraction & Scoring Lambda (DEV)", fontcolor="black", color=COLOR_MAPPING["Lambda"])
                extraction_qa = Lambda("Extraction & Scoring Lambda (QA)", fontcolor="black", color=COLOR_MAPPING["Lambda"])

            # SQS Queues
            with Cluster("SQS Queues"):
                extraction_queue_dev = SQS("Extraction Queue (DEV)", fontcolor="black", color=COLOR_MAPPING["SQS"])
                extraction_queue_qa = SQS("Extraction Queue (QA)", fontcolor="black", color=COLOR_MAPPING["SQS"])
                fallback_queue_dev = SQS("Fallback Queue (DEV)", fontcolor="black", color=COLOR_MAPPING["SQS"])
                fallback_queue_qa = SQS("Fallback Queue (QA)", fontcolor="black", color=COLOR_MAPPING["SQS"])

            # Bedrock Models
            with Cluster("Amazon Bedrock Models"):
                primary_model = Bedrock("Nova Pro v1", fontcolor="black", color=COLOR_MAPPING["Model"])
                fallback_model = Bedrock("Claude Sonnet 4", fontcolor="black", color=COLOR_MAPPING["Model"])

            # IAM Roles
            with Cluster("IAM Roles"):
                classification_role_dev = IAM("Classification Role (DEV)", fontcolor="black", color=COLOR_MAPPING["IAM"])
                classification_role_qa = IAM("Classification Role (QA)", fontcolor="black", color=COLOR_MAPPING["IAM"])
                extraction_role_dev = IAM("Extraction Role (DEV)", fontcolor="black", color=COLOR_MAPPING["IAM"])
                extraction_role_qa = IAM("Extraction Role (QA)", fontcolor="black", color=COLOR_MAPPING["IAM"])

            # DEV Environment Flow
            filing_desk_dev >> Edge(label="ObjectCreated event") >> classification_dev
            classification_dev >> extraction_queue_dev
            extraction_queue_dev >> extraction_dev
            extraction_dev >> Edge(label="High Score") >> results_dev
            extraction_dev >> Edge(label="Low Score") >> fallback_queue_dev

            # QA Environment Flow
            filing_desk_qa >> Edge(label="ObjectCreated event") >> classification_qa
            classification_qa >> extraction_queue_qa
            extraction_queue_qa >> extraction_qa
            extraction_qa >> Edge(label="High Score") >> results_qa
            extraction_qa >> Edge(label="Low Score") >> fallback_queue_qa

            # Model Usage (using dotted lines)
            classification_dev >> Edge(style="dotted") >> primary_model
            classification_dev >> Edge(style="dotted", label="Fallback") >> fallback_model
            extraction_dev >> Edge(style="dotted") >> primary_model
            extraction_dev >> Edge(style="dotted", label="Fallback") >> fallback_model
            classification_qa >> Edge(style="dotted") >> primary_model
            classification_qa >> Edge(style="dotted", label="Fallback") >> fallback_model
            extraction_qa >> Edge(style="dotted") >> primary_model
            extraction_qa >> Edge(style="dotted", label="Fallback") >> fallback_model

            # IAM Role Associations
            classification_role_dev >> Edge(style="dotted") >> classification_dev
            classification_role_qa >> Edge(style="dotted") >> classification_qa
            extraction_role_dev >> Edge(style="dotted") >> extraction_dev
            extraction_role_qa >> Edge(style="dotted") >> extraction_qa

if __name__ == "__main__":
    print("Generating high-level architecture diagram...")
    generate_high_level_diagram()
    print("High-level architecture diagram generated successfully.")

    print("Generating detailed architecture diagram...")
    generate_detailed_diagram()
    print("Detailed architecture diagram generated successfully.")

    print("Diagrams have been saved to documentation/architecture/v2/generated_diagrams/")
