"""Core data models for the graph reasoning engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ReasoningType(Enum):
    """Classification of user query intent for graph routing."""

    ENTITY_LOOKUP = "entity_lookup"
    RELATIONSHIP = "relationship"
    MULTI_HOP = "multi_hop"
    AGGREGATION = "aggregation"
    TEMPORAL = "temporal"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    EXPLORATION = "exploration"


@dataclass
class DecomposedQuery:
    """Result of rule-based query decomposition."""

    reasoning_type: ReasoningType
    entities: list[str]
    relationships: list[str]
    time_range: tuple[datetime, datetime] | None
    aggregation_fn: str | None
    hop_limit: int
    confidence: float


@dataclass
class ReasoningStep:
    """A single atomic reasoning step."""

    step_number: int
    operation: str  # "lookup", "traverse", "compare", "aggregate", "infer"
    description: str
    evidence: list[str]
    confidence: float  # 0.0-1.0


@dataclass
class ReasoningChain:
    """Complete reasoning chain ready for LLM narration."""

    query: str
    reasoning_type: str
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    evidence_summary: str = ""
    total_confidence: float = 0.0
    source_count: int = 0

    def to_llm_prompt_context(self) -> str:
        """
        Format the chain as structured context for the small LLM.

        This is the KEY format — it must be dense, unambiguous,
        and require ZERO reasoning from the LLM.
        """
        lines: list[str] = []
        lines.append(f"QUERY: {self.query}")
        lines.append(f"REASONING TYPE: {self.reasoning_type}")
        lines.append(f"CONFIDENCE: {self.total_confidence:.0%}")
        lines.append(f"SOURCES: {self.source_count} items analyzed")
        lines.append("")
        lines.append("REASONING CHAIN:")

        for step in self.steps:
            lines.append(
                f"  Step {step.step_number} [{step.operation}]: {step.description}"
            )
            for evidence in step.evidence:
                lines.append(f"    • {evidence}")

        lines.append("")
        lines.append(f"CONCLUSION: {self.conclusion}")
        lines.append("")
        lines.append(f"EVIDENCE SUMMARY: {self.evidence_summary}")

        return "\n".join(lines)
