import json, logging, os
from typing import Dict, Any

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