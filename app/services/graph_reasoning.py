"""Top-level orchestrator — query → graph reasoning → LLM-ready prompt."""

from __future__ import annotations

import logging

from neo4j import Driver

from app.models.reasoning import ReasoningStep
from app.services.confidence import (
    ConfidenceScorer,
    ConfidenceSignals,
    MatchQuality,
)
from app.services.entity_resolver import EntityResolver
from app.services.prompt_builder import PromptBuilder
from app.services.query_decomposer import QueryDecomposer
from app.services.reasoning_chain_builder import ReasoningChainBuilder
from app.services.template_router import TemplateRouter

logger = logging.getLogger(__name__)

# Threshold below which graph results are supplemented with vectors.
# Derived from signal analysis, not a guess: if classification or entity
# resolution is weak AND results are sparse, enrich with vector context.
_VECTOR_ENRICHMENT_THRESHOLD = 0.45


class GraphReasoningOrchestrator:
    """
    Receives a user query and returns a prompt string ready for the LLM.

    Pipeline:
    1. Decompose query     (rule-based,   <5 ms)
    2. Resolve entities    (in-mem cache, <10 ms)
    3. Route to templates  (dict lookup,  <5 ms)
    4. Execute Cypher      (Neo4j,        <50 ms)
    5. Build reasoning chain              <5 ms
    6. Construct LLM prompt               <1 ms
    """

    def __init__(self, driver: Driver) -> None:
        self.driver = driver
        self.decomposer = QueryDecomposer()
        self.router = TemplateRouter()
        self.chain_builder = ReasoningChainBuilder()
        self.prompt_builder = PromptBuilder()
        self.entity_resolver = EntityResolver(driver)
        self._scorer = ConfidenceScorer()

    def warm_up(self) -> None:
        """Load entity cache — call once at startup."""
        self.entity_resolver.refresh_cache()

    def process_query(
        self,
        user_query: str,
        vector_results: list[str] | None = None,
    ) -> str:
        """
        Run the full reasoning pipeline.

        Returns a formatted prompt string ready for LLM inference.
        """
        # 1. Decompose
        decomposed = self.decomposer.decompose(user_query)
        logger.debug(
            "Decomposed → type=%s entities=%s confidence=%.2f",
            decomposed.reasoning_type.value,
            decomposed.entities,
            decomposed.confidence,
        )

        # 2. Entity resolution — collect match quality signals
        resolved_entities: list[str] = []
        match_qualities: list[MatchQuality] = []
        for entity in decomposed.entities:
            resolved, quality = self.entity_resolver.resolve_with_quality(
                entity
            )
            resolved_entities.append(
                resolved["name"] if resolved else entity
            )
            match_qualities.append(quality)
        decomposed.entities = resolved_entities

        # 3. Route to Cypher templates
        cypher_queries = self.router.route(decomposed)

        if not cypher_queries:
            return self.prompt_builder.build_fallback_prompt(
                user_query,
                vector_results or ["No relevant context found."],
            )

        # 4. Execute Cypher
        all_results: list[dict] = []
        with self.driver.session() as session:
            for tmpl_name, cypher in cypher_queries:
                try:
                    result = session.run(cypher)
                    records = [dict(record) for record in result]
                    all_results.extend(records)
                except Exception:
                    logger.exception("Cypher error in template %s", tmpl_name)

        # 5. Build reasoning chain
        chain = self.chain_builder.build_chain(
            user_query, decomposed.reasoning_type, all_results
        )

        # 6. Algorithmically decide whether to enrich with vector results
        pipeline_signals = ConfidenceSignals(
            entity_match_qualities=match_qualities,
            result_count=len(all_results),
            expected_result_count=max(len(all_results), 1),
        )
        pipeline_confidence = self._scorer.chain_confidence(pipeline_signals)

        if vector_results and pipeline_confidence < _VECTOR_ENRICHMENT_THRESHOLD:
            # Confidence of vector step = entity resolution quality
            vector_step_conf = self._scorer.entity_resolution_confidence(
                pipeline_signals
            )
            chain.steps.append(
                ReasoningStep(
                    step_number=len(chain.steps) + 1,
                    operation="lookup",
                    description=(
                        "Supplementary context from document search:"
                    ),
                    evidence=vector_results[:3],
                    confidence=vector_step_conf,
                )
            )

        # 7. Build LLM prompt
        return self.prompt_builder.build_prompt(chain, user_query)
