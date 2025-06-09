import json, logging, os
from typing import Dict, Any
from pathlib import Path, PurePosixPath
from string import Template

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def add_now_process(folder_path):
    now_process = (
        f"\nNOW PROCESS:\n"
        f"Folder path: `{folder_path}`\n"
        f"Extracted text follows the PDF below."
    )

    return now_process

def get_instructions(action: str) -> str:
    """
    Load instruction content from files.
    """
    task_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())
    base_path = task_root
    mapping = {
        "user": os.path.join(base_path, "instructions/user.txt"),
        "system": os.path.join(base_path, "instructions/system.txt")
    }
    fn = mapping.get(action)
    if fn and os.path.exists(fn):
        with open(fn, 'r', encoding='utf-8') as file:
            return file.read()
    return ""

def get_instructions_extraction(action: str, system_p: str, user_p: str, source_category: str) -> Template:
    """
    Load instruction templates based on category and prompt type for extraction.

    Args:
        action: The type of instruction to load (user or system)
        system_p: The system prompt file name
        user_p: The user prompt file name
        source_category: The category of the document

    Returns:
        Template: A string Template object with the instruction content
    """
    task_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())
    mapping = {
        "user": os.path.join(task_root, f"instructions/{source_category}/{user_p}.txt"),
        "system": os.path.join(task_root, f"instructions/{source_category}/{system_p}.txt")
    }
    fn = mapping.get(action)

    if fn and os.path.exists(fn):
        with open(fn, 'r', encoding='utf-8') as file:
            return Template(file.read())

    # Fallback to default
    default_path = os.path.join(task_root, f"instructions/{source_category}/user.txt")
    if os.path.exists(default_path):
        with open(default_path, 'r', encoding='utf-8') as file:
            return Template(file.read())

    # If no template found, return empty template
    return Template("")

def build_user_prompt_extraction(
    pdf_path: str,
    document_number: str,
    document_type: str,
    category: str,
    system_p: str,
    user_p: str,
) -> str:
    """
    Render the user prompt with the runtime values for extraction.

    Args:
        pdf_path: The path to the PDF file
        document_number: The document number
        document_type: The type of document
        category: The category of the document
        system_p: The system prompt file name
        user_p: The user prompt file name

    Returns:
        str: The rendered user prompt
    """
    # Build the S3/local key where the JSON should be saved
    save_key = PurePosixPath(
        category,
        document_number,
        f"{category}_{document_number}.json"
    )

    # Load the Template
    user_tmpl = get_instructions_extraction("user", system_p, user_p, category)

    # Substitute into the Template
    final_prompt = user_tmpl.substitute(
        pdf_path=pdf_path,
        document_number=document_number,
        document_type=document_type,
        category=category,
        save_key=save_key
    )

    return final_prompt

def build_system_prompt_extraction(
    schema_path: str,
    examples_dir: str,
    system_p: str,
    user_p: str,
    category: str
) -> str:
    """
    Build the system prompt by injecting the JSON schema and
    all example JSON outputs into the prompt template for extraction.

    Args:
        schema_path: The path to the JSON schema file
        examples_dir: The directory containing example JSON files
        system_p: The system prompt file name
        user_p: The user prompt file name
        category: The category of the document

    Returns:
        str: The rendered system prompt
    """
    # Load the schema
    if os.path.exists(schema_path):
        schema = Path(schema_path).read_text().strip()
    else:
        logger.warning(f"Schema file not found: {schema_path}")
        schema = "{}"

    # Load each example and wrap in ```json ... ``` fences
    example_blocks = []
    if os.path.exists(examples_dir):
        for example_file in Path(examples_dir).glob("*.json"):
            content = Path(example_file).read_text().strip()
            example_blocks.append(f"```json\n{content}\n```")
    else:
        logger.warning(f"Examples directory not found: {examples_dir}")

    # Join all example blocks with spacing
    examples_section = "\n\n".join(example_blocks)

    # Get the system template
    SYSTEM_TEMPLATE = get_instructions_extraction("system", system_p, user_p, category)

    # Substitute into the template
    prompt = SYSTEM_TEMPLATE.substitute(
        schema=schema,
        examples_section=examples_section
    )

    return prompt
