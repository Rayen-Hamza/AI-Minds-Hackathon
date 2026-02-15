"""Tests for the ReasoningChain data model — formatting for LLM context."""

from __future__ import annotations

from app.models.reasoning import (
    DecomposedQuery,
    ReasoningChain,
    ReasoningStep,
    ReasoningType,
)


# ─────────────────────────────────────────────────────────────────────
# ReasoningType enum
# ─────────────────────────────────────────────────────────────────────


class TestReasoningType:
    def test_all_values(self):
        expected = {
            "entity_lookup", "relationship", "multi_hop", "aggregation",
            "temporal", "comparison", "causal", "exploration",
        }
        actual = {rt.value for rt in ReasoningType}
        assert actual == expected

    def test_enum_lookup(self):
        assert ReasoningType("entity_lookup") == ReasoningType.ENTITY_LOOKUP


# ─────────────────────────────────────────────────────────────────────
# ReasoningChain.to_llm_prompt_context
# ─────────────────────────────────────────────────────────────────────


class TestToLLMPromptContext:
    def test_contains_query(self):
        chain = ReasoningChain(query="who is Alice?", reasoning_type="entity_lookup")
        ctx = chain.to_llm_prompt_context()
        assert "QUERY: who is Alice?" in ctx

    def test_contains_reasoning_type(self):
        chain = ReasoningChain(query="q", reasoning_type="causal")
        ctx = chain.to_llm_prompt_context()
        assert "REASONING TYPE: causal" in ctx

    def test_contains_confidence_percent(self):
        chain = ReasoningChain(
            query="q", reasoning_type="x", total_confidence=0.85
        )
        ctx = chain.to_llm_prompt_context()
        assert "CONFIDENCE: 85%" in ctx

    def test_contains_steps(self):
        chain = ReasoningChain(query="q", reasoning_type="x")
        chain.steps.append(
            ReasoningStep(
                step_number=1,
                operation="lookup",
                description="Found Alice.",
                evidence=["name: Alice", "role: Engineer"],
                confidence=0.9,
            )
        )
        ctx = chain.to_llm_prompt_context()
        assert "Step 1 [lookup]: Found Alice." in ctx
        assert "• name: Alice" in ctx
        assert "• role: Engineer" in ctx

    def test_contains_conclusion(self):
        chain = ReasoningChain(
            query="q", reasoning_type="x", conclusion="She is an engineer."
        )
        ctx = chain.to_llm_prompt_context()
        assert "CONCLUSION: She is an engineer." in ctx

    def test_contains_evidence_summary(self):
        chain = ReasoningChain(
            query="q", reasoning_type="x",
            evidence_summary="Based on 3 lookups."
        )
        ctx = chain.to_llm_prompt_context()
        assert "EVIDENCE SUMMARY: Based on 3 lookups." in ctx

    def test_empty_chain_format(self):
        chain = ReasoningChain(query="q", reasoning_type="x")
        ctx = chain.to_llm_prompt_context()
        assert "REASONING CHAIN:" in ctx
        assert "CONCLUSION:" in ctx

    def test_source_count(self):
        chain = ReasoningChain(
            query="q", reasoning_type="x", source_count=42
        )
        ctx = chain.to_llm_prompt_context()
        assert "42 items analyzed" in ctx


# ─────────────────────────────────────────────────────────────────────
# DecomposedQuery defaults
# ─────────────────────────────────────────────────────────────────────


class TestDecomposedQuery:
    def test_fields(self):
        dq = DecomposedQuery(
            reasoning_type=ReasoningType.CAUSAL,
            entities=["Alice"],
            relationships=["works on"],
            time_range=None,
            aggregation_fn=None,
            hop_limit=5,
            confidence=0.85,
        )
        assert dq.reasoning_type == ReasoningType.CAUSAL
        assert dq.entities == ["Alice"]
        assert dq.hop_limit == 5
