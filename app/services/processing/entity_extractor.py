"""
Named Entity Recognition (NER) using spaCy.
Extracts entities like persons, organizations, locations, dates, etc.
"""

import logging
from typing import Optional
import spacy
from spacy.language import Language

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    Wrapper for spaCy NER to extract entities from text.
    Uses en_core_web_sm model for efficient entity extraction.
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize entity extractor.

        Args:
            model_name: spaCy model name (download with: python -m spacy download en_core_web_sm)
        """
        self.model_name = model_name
        self._nlp: Optional[Language] = None
        logger.info(f"Initialized EntityExtractor with model: {model_name}")

    def _load_model(self) -> None:
        """Lazy-load spaCy model on first use."""
        try:
            logger.info(f"Loading spaCy model: {self.model_name}")
            self._nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model successfully")

        except OSError as e:
            logger.error(
                f"spaCy model '{self.model_name}' not found. "
                f"Install with: python -m spacy download {self.model_name}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {e}")
            raise

    @property
    def nlp(self) -> Language:
        """Get or load spaCy model."""
        if self._nlp is None:
            self._load_model()
        return self._nlp

    def extract_entities(
        self,
        text: str,
        entity_types: Optional[list[str]] = None
    ) -> list[str]:
        """
        Extract named entities from text.

        Args:
            text: Input text
            entity_types: Filter by specific entity types (e.g., ["PERSON", "ORG", "LOC"])
                         If None, extracts all types.

        Returns:
            List of unique entity texts
        """
        try:
            if not text or not text.strip():
                return []

            # Process text with spaCy
            doc = self.nlp(text)

            # Extract entities
            entities = []
            for ent in doc.ents:
                # Filter by type if specified
                if entity_types is None or ent.label_ in entity_types:
                    entities.append(ent.text)

            # Return unique entities while preserving order
            unique_entities = list(dict.fromkeys(entities))

            logger.debug(
                f"Extracted {len(unique_entities)} entities from text "
                f"({len(text)} chars): {unique_entities[:5]}"
            )

            return unique_entities

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []

    def extract_entities_with_labels(
        self,
        text: str,
        entity_types: Optional[list[str]] = None
    ) -> list[dict[str, str]]:
        """
        Extract entities with their labels.

        Args:
            text: Input text
            entity_types: Filter by specific entity types

        Returns:
            List of dicts with 'text' and 'label' keys
        """
        try:
            if not text or not text.strip():
                return []

            doc = self.nlp(text)

            entities = []
            for ent in doc.ents:
                if entity_types is None or ent.label_ in entity_types:
                    entities.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char
                    })

            return entities

        except Exception as e:
            logger.error(f"Error extracting labeled entities: {e}")
            return []

    def extract_key_entities(self, text: str) -> dict[str, list[str]]:
        """
        Extract and categorize key entity types.

        Args:
            text: Input text

        Returns:
            Dict mapping entity type to list of entities
        """
        try:
            if not text or not text.strip():
                return {}

            doc = self.nlp(text)

            # Categorize entities
            categorized = {
                "persons": [],
                "organizations": [],
                "locations": [],
                "dates": [],
                "other": []
            }

            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    categorized["persons"].append(ent.text)
                elif ent.label_ in ["ORG", "ORGANIZATION"]:
                    categorized["organizations"].append(ent.text)
                elif ent.label_ in ["GPE", "LOC", "LOCATION"]:
                    categorized["locations"].append(ent.text)
                elif ent.label_ in ["DATE", "TIME"]:
                    categorized["dates"].append(ent.text)
                else:
                    categorized["other"].append(ent.text)

            # Remove duplicates while preserving order
            for key in categorized:
                categorized[key] = list(dict.fromkeys(categorized[key]))

            return categorized

        except Exception as e:
            logger.error(f"Error extracting key entities: {e}")
            return {}

    def extract_batch(
        self,
        texts: list[str],
        entity_types: Optional[list[str]] = None
    ) -> list[list[str]]:
        """
        Extract entities from multiple texts efficiently.

        Args:
            texts: List of input texts
            entity_types: Filter by specific entity types

        Returns:
            List of entity lists (one per input text)
        """
        try:
            if not texts:
                return []

            logger.info(f"Extracting entities from {len(texts)} texts")

            # Batch process with spaCy for efficiency
            results = []
            for doc in self.nlp.pipe(texts, batch_size=50):
                entities = []
                for ent in doc.ents:
                    if entity_types is None or ent.label_ in entity_types:
                        entities.append(ent.text)

                # Unique entities
                unique_entities = list(dict.fromkeys(entities))
                results.append(unique_entities)

            return results

        except Exception as e:
            logger.error(f"Error in batch entity extraction: {e}")
            return [[] for _ in texts]


# Global singleton instance
_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor(model_name: str = "en_core_web_sm") -> EntityExtractor:
    """
    Get or create global EntityExtractor instance.

    Args:
        model_name: spaCy model name

    Returns:
        EntityExtractor instance
    """
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor(model_name)
    return _entity_extractor
