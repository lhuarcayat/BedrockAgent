from pydantic import BaseModel
from typing import Literal, Optional

class ClassMeta(BaseModel):
    """
    Pydantic schema for classification results.
    """
    document_number: str
    document_type: Literal["person", "company"]
    category: Literal["CERL", "CECRL", "RUT", "RUB", "ACC", "BLANK", "LINK_ONLY"]
    path: str
    text: Optional[str] = None
