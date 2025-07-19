"""
Webhook-related data models
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from .base import ActionType


class WebhookPayload(BaseModel):
    """Payload received from Frappe webhooks"""
    doctype: str = Field(..., description="Type of the document")
    docname: str = Field(..., description="Name/ID of the document")
    action: ActionType = Field(..., description="Action that triggered the webhook")
    data: Optional[Dict[str, Any]] = Field(None, description="Document data (for create/update actions)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the webhook was triggered")