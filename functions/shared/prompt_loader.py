"""
Prompt loading utilities for Lambda functions.

This module handles loading classification and extraction prompts from filesystem.
Uses Option A: read files each invocation for reliability and consistency.
"""

import os
import logging
from pathlib import Path
from string import Template
from typing import Tuple, Dict

logger = logging.getLogger(__name__)

class PromptLoader:
    """
    Handles loading prompts from filesystem.
    Uses read-every-time approach for reliability in production.
    """
    
    def __init__(self):
        self.task_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())
        logger.info(f"PromptLoader initialized with task_root: {self.task_root}")
    
    def get_classification_prompts(self) -> Tuple[str, str]:
        """
        Get classification prompts (system, user).
        Reads from filesystem each time for consistency.
        
        Returns:
            tuple: (system_prompt, user_prompt)
        """
        try:
            system_path = Path(self.task_root) / "instructions" / "system.txt"
            user_path = Path(self.task_root) / "instructions" / "user.txt"
            
            if not system_path.exists():
                raise FileNotFoundError(f"System prompt not found: {system_path}")
            if not user_path.exists():
                raise FileNotFoundError(f"User prompt not found: {user_path}")
            
            system_prompt = system_path.read_text(encoding='utf-8')
            user_prompt = user_path.read_text(encoding='utf-8')
            
            logger.debug(f"Classification prompts loaded: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
            
            return system_prompt, user_prompt
            
        except Exception as e:
            logger.error(f"Error loading classification prompts: {e}")
            raise
    
    def get_extraction_prompts(self, category: str) -> Tuple[str, str]:
        """
        Get extraction prompts for a specific category.
        
        Args:
            category: Document category (CERL, CECRL, RUT, RUB, ACC)
            
        Returns:
            tuple: (system_prompt, user_prompt)
        """
        try:
            system_path = Path(self.task_root) / "instructions" / category / "system.txt"
            user_path = Path(self.task_root) / "instructions" / category / "user.txt"
            
            if not system_path.exists():
                raise FileNotFoundError(f"System prompt not found for {category}: {system_path}")
            if not user_path.exists():
                raise FileNotFoundError(f"User prompt not found for {category}: {user_path}")
            
            system_prompt = system_path.read_text(encoding='utf-8')
            user_prompt = user_path.read_text(encoding='utf-8')
            
            logger.debug(f"Extraction prompts loaded for {category}: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
            
            return system_prompt, user_prompt
            
        except Exception as e:
            logger.error(f"Error loading extraction prompts for {category}: {e}")
            raise
    
# Global instance for Lambda usage
prompt_loader = PromptLoader()
