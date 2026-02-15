"""
Data models for the memory layer.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class Event(BaseModel):
    """A conversation event to be stored in Qdrant."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Profile(BaseModel):
    """User profile with properties and preferences."""

    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Factual attributes (name, role, location, etc.)",
    )
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Likes, dislikes, style preferences, interests",
    )
    updated_at: datetime = Field(default_factory=datetime.now)

    def merge(self, new_data: Dict[str, Any]) -> None:
        """
        Merge new data into the profile.
        New keys are inserted, existing keys are overwritten.
        List values are extended with unique items.
        """
        for key, value in new_data.items():
            if key == "properties" and isinstance(value, dict):
                for prop_key, prop_value in value.items():
                    if isinstance(prop_value, list) and prop_key in self.properties:
                        # Extend list with unique items
                        existing = self.properties[prop_key]
                        if isinstance(existing, list):
                            self.properties[prop_key] = list(
                                set(existing + prop_value)
                            )
                        else:
                            self.properties[prop_key] = prop_value
                    else:
                        self.properties[prop_key] = prop_value

            elif key == "preferences" and isinstance(value, dict):
                for pref_key, pref_value in value.items():
                    if isinstance(pref_value, list) and pref_key in self.preferences:
                        # Extend list with unique items
                        existing = self.preferences[pref_key]
                        if isinstance(existing, list):
                            self.preferences[pref_key] = list(
                                set(existing + pref_value)
                            )
                        else:
                            self.preferences[pref_key] = pref_value
                    else:
                        self.preferences[pref_key] = pref_value

        self.updated_at = datetime.now()


class ExtractedFacts(BaseModel):
    """Facts extracted from a conversation."""

    properties: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
