"""Tests for the PromptBuilder — structured prompts for sub-4B LLMs."""

from __future__ import annotations

import pytest

from app.models.reasoning import ReasoningChain, ReasoningStep
from app.services.prompt_builder import PromptBuilder


@pytest.fixture
def builder() -> PromptBuilder:
    return PromptBuilder()


def _make_chain(
    num_steps: int = 2,
    conclusion: str = "Found the answer.",
    confidence: float = 0.85,
) -> ReasoningChain:
    steps = [
        ReasoningStep(
            step_number=i + 1,
            operation="lookup",
            description=f"Step {i + 1} description.",
            evidence=[f"Evidence item {i + 1}"],
            confidence=0.9,
        )
        for i in range(num_steps)
    ]
    return ReasoningChain(
        query="test query",
        reasoning_type="entity_lookup",
        steps=steps,
        conclusion=conclusion,
        evidence_summary="2 items analyzed",
        total_confidence=confidence,
        source_count=num_steps,
    )


# ─────────────────────────────────────────────────────────────────────
# build_prompt
# ─────────────────────────────────────────────────────────────────────


class TestBuildPrompt:
    def test_contains_system_prompt(self, builder: PromptBuilder):
        chain = _make_chain()
        prompt = builder.build_prompt(chain, "who is Alice?")
        assert "NARRATE" in prompt
        assert "RULES" in prompt

    def test_contains_user_query(self, builder: PromptBuilder):
        chain = _make_chain()
        prompt = builder.build_prompt(chain, "who is Alice?")
        assert "who is Alice?" in prompt

    def test_contains_reasoning_chain(self, builder: PromptBuilder):
        chain = _make_chain(conclusion="Alice is an engineer.")
        prompt = builder.build_prompt(chain, "who is Alice?")
        assert "Alice is an engineer." in prompt
        assert "REASONING CHAIN:" in prompt

    def test_contains_response_marker(self, builder: PromptBuilder):
        chain = _make_chain()
        prompt = builder.build_prompt(chain, "q")
        assert "RESPONSE:" in prompt

    def test_contains_confidence(self, builder: PromptBuilder):
        chain = _make_chain(confidence=0.85)
        prompt = builder.build_prompt(chain, "q")
        assert "85%" in prompt

    def test_contains_step_evidence(self, builder: PromptBuilder):
        chain = _make_chain()
        prompt = builder.build_prompt(chain, "q")
        assert "Evidence item 1" in prompt
        assert "Step 1" in prompt


# ─────────────────────────────────────────────────────────────────────
# build_fallback_prompt
# ─────────────────────────────────────────────────────────────────────


class TestBuildFallbackPrompt:
    def test_contains_sources(self, builder: PromptBuilder):
        prompt = builder.build_fallback_prompt(
            "who is Alice?",
            ["Alice is an engineer at Acme.", "She works on ML."],
        )
        assert "Alice is an engineer at Acme." in prompt
        assert "[Source 1]" in prompt
        assert "[Source 2]" in prompt

    def test_contains_user_query(self, builder: PromptBuilder):
        prompt = builder.build_fallback_prompt("who is Alice?", ["ctx"])
        assert "who is Alice?" in prompt

    def test_limits_to_five_sources(self, builder: PromptBuilder):
        chunks = [f"Chunk {i}" for i in range(10)]
        prompt = builder.build_fallback_prompt("q", chunks)
        assert "[Source 5]" in prompt
        assert "[Source 6]" not in prompt

    def test_includes_grounding_instruction(self, builder: PromptBuilder):
        prompt = builder.build_fallback_prompt("q", ["ctx"])
        assert "ONLY" in prompt


# ─────────────────────────────────────────────────────────────────────
# Truncation
# ─────────────────────────────────────────────────────────────────────


class TestTruncation:
    def test_long_context_is_truncated(self, builder: PromptBuilder):
        # Create a chain with very long evidence
        steps = [
            ReasoningStep(
                step_number=1,
                operation="lookup",
                description="Big step.",
                evidence=[f"word " * 200],  # ~200 words per evidence
                confidence=0.9,
            )
            for _ in range(10)
        ]
        chain = ReasoningChain(
            query="q",
            reasoning_type="entity_lookup",
            steps=steps,
            conclusion="Done.",
            total_confidence=0.9,
            source_count=10,
        )
        prompt = builder.build_prompt(chain, "q")
        # Should have been truncated
        word_count = len(prompt.split())
        # System prompt + context + query ≈ shouldn't be astronomical
        assert word_count < 2000

    def test_truncation_preserves_conclusion(self, builder: PromptBuilder):
        steps = [
            ReasoningStep(
                step_number=1,
                operation="lookup",
                description="Big step.",
                evidence=[f"word " * 300],
                confidence=0.9,
            )
            for _ in range(5)
        ]
        chain = ReasoningChain(
            query="q",
            reasoning_type="entity_lookup",
            steps=steps,
            conclusion="THE FINAL CONCLUSION",
            total_confidence=0.9,
            source_count=5,
        )
        prompt = builder.build_prompt(chain, "q")
        assert "CONCLUSION" in prompt


# ─────────────────────────────────────────────────────────────────────
# System prompt constraints
# ─────────────────────────────────────────────────────────────────────


class TestSystemPrompt:
    def test_no_hallucination_rule(self, builder: PromptBuilder):
        assert "hallucinate" in builder.SYSTEM_PROMPT.lower()

    def test_narration_only(self, builder: PromptBuilder):
        assert "NARRATE" in builder.SYSTEM_PROMPT

    def test_source_count_rule(self, builder: PromptBuilder):
        assert "sources" in builder.SYSTEM_PROMPT.lower()
