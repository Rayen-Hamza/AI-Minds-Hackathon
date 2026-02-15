"""
Profile storage with JSON persistence.
Simplified single-user profile management.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .models import Profile

logger = logging.getLogger(__name__)


class ProfileStore:
    """Manages user profile persistence to disk."""

    def __init__(self, profile_path: Optional[Path] = None):
        """
        Initialize profile store.

        Args:
            profile_path: Path to profile JSON file. Defaults to data/profile.json
        """
        if profile_path is None:
            # Default to data directory in project root
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            profile_path = data_dir / "user_profile.json"

        self.profile_path = Path(profile_path)
        logger.info(f"Profile store initialized at: {self.profile_path}")

    def load(self) -> Profile:
        """
        Load profile from disk.

        Returns:
            Profile object (empty if file doesn't exist)
        """
        if not self.profile_path.exists():
            logger.info("No existing profile found, creating new one")
            return Profile()

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Profile(**data)
        except Exception as e:
            logger.error(f"Error loading profile: {e}")
            return Profile()

    def save(self, profile: Profile) -> bool:
        """
        Save profile to disk.

        Args:
            profile: Profile object to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict and save
            data = profile.model_dump(mode="json")

            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Profile saved successfully to {self.profile_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            return False

    def update(self, new_data: dict) -> Profile:
        """
        Load profile, merge new data, and save.

        Args:
            new_data: Dictionary with 'properties' and/or 'preferences' to merge

        Returns:
            Updated profile
        """
        profile = self.load()
        profile.merge(new_data)
        self.save(profile)
        return profile

    def clear(self) -> bool:
        """
        Clear the profile (delete file).

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.profile_path.exists():
                self.profile_path.unlink()
                logger.info("Profile cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing profile: {e}")
            return False
