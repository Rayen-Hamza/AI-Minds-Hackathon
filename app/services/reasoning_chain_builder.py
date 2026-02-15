"""Transforms raw Neo4j results into structured reasoning chains."""

from __future__ import annotations

from app.models.reasoning import ReasoningChain, ReasoningStep, ReasoningType
from app.services.confidence import ConfidenceScorer, ConfidenceSignals


class ReasoningChainBuilder:
    """
    Transforms raw Neo4j query results into structured reasoning chains.

    This is where the 'intelligence' lives — deterministic graph logic,
    NOT LLM inference.
    """

    def __init__(self) -> None:
        self._scorer = ConfidenceScorer()

    def build_chain(
        self,
        query: str,
        reasoning_type: ReasoningType,
        cypher_results: list[dict],
    ) -> ReasoningChain:
        """Dispatch to type-specific chain builder."""
        builders = {
            ReasoningType.ENTITY_LOOKUP: self._build_entity_chain,
            ReasoningType.RELATIONSHIP: self._build_relationship_chain,
            ReasoningType.MULTI_HOP: self._build_multi_hop_chain,
            ReasoningType.AGGREGATION: self._build_aggregation_chain,
            ReasoningType.TEMPORAL: self._build_temporal_chain,
            ReasoningType.COMPARISON: self._build_comparison_chain,
            ReasoningType.CAUSAL: self._build_causal_chain,
            ReasoningType.EXPLORATION: self._build_exploration_chain,
        }
        builder = builders.get(reasoning_type, self._build_generic_chain)
        chain = builder(query, cypher_results)

        # Algorithmic chain confidence from real signals
        signals = ConfidenceSignals(
            result_count=len(cypher_results),
            expected_result_count=max(len(cypher_results), 1),
            evidence_completeness=self._measure_completeness(cypher_results),
        )
        chain.total_confidence = self._scorer.chain_confidence(signals)
        return chain

    # ── Entity Lookup ────────────────────────────────────────────────

    def _build_entity_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="entity_lookup")

        if not results:
            chain.steps.append(
                ReasoningStep(
                    step_number=1,
                    operation="lookup",
                    description="No matching entity found in knowledge graph.",
                    evidence=[],
                    confidence=0.0,
                )
            )
            chain.conclusion = (
                "Entity not found in your personal knowledge base."
            )
            return chain

        entity = results[0]
        chain.source_count = 1

        # Step 1 — identity
        evidence_items = [
            f"{k}: {v}"
            for k, v in entity.items()
            if v and v != [] and v != ""
        ]
        chain.steps.append(
            ReasoningStep(
                step_number=1,
                operation="lookup",
                description="Found entity matching query.",
                evidence=evidence_items,
                confidence=self._scorer.step_confidence(entity),
            )
        )

        # Step 2 — connections
        connection_fields = {
            "organizations",
            "expertise",
            "projects",
            "related_topics",
            "subtopics",
            "topics",
        }
        connections = {
            k: v for k, v in entity.items() if k in connection_fields and v
        }
        if connections:
            chain.steps.append(
                ReasoningStep(
                    step_number=2,
                    operation="traverse",
                    description="Retrieved connected entities.",
                    evidence=[
                        (
                            f"{k}: {', '.join(v)}"
                            if isinstance(v, list)
                            else f"{k}: {v}"
                        )
                        for k, v in connections.items()
                    ],
                    confidence=self._scorer.step_confidence(
                        connections,
                        expected_keys=list(connection_fields),
                    ),
                )
            )

        chain.conclusion = self._summarize_entity(entity)
        chain.evidence_summary = (
            f"Based on {len(chain.steps)} graph lookups."
        )
        return chain

    # ── Relationship ─────────────────────────────────────────────────

    def _build_relationship_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="relationship")
        if not results:
            chain.conclusion = "No relationships found."
            return chain

        chain.source_count = len(results)
        for i, r in enumerate(results[:10]):
            chain.steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    operation="traverse",
                    description="Found connection.",
                    evidence=[
                        f"{k}: {v}"
                        for k, v in r.items()
                        if v and v != []
                    ],
                    confidence=self._scorer.step_confidence(r),
                )
            )
        chain.conclusion = f"Found {len(results)} connected items."
        return chain

    # ── Multi-Hop ────────────────────────────────────────────────────

    def _build_multi_hop_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="multi_hop")

        if not results:
            chain.steps.append(
                ReasoningStep(
                    step_number=1,
                    operation="traverse",
                    description="No path found between the specified entities.",
                    evidence=[
                        "Entities may not be connected within the "
                        "knowledge graph."
                    ],
                    confidence=0.0,
                )
            )
            chain.conclusion = "No connection found."
            return chain

        for i, path_result in enumerate(results):
            path_nodes = path_result.get("path_nodes", [])
            path_rels = path_result.get("path_relationships", [])
            path_length = path_result.get("path_length", 0)

            step_desc_parts: list[str] = []
            for j in range(len(path_nodes) - 1):
                source = path_nodes[j]
                target = path_nodes[j + 1]
                rel = (
                    path_rels[j] if j < len(path_rels) else "CONNECTED_TO"
                )
                step_desc_parts.append(
                    f"{source.get('name', '?')} ({source.get('type', '?')}) "
                    f"—[{rel}]→ "
                    f"{target.get('name', '?')} ({target.get('type', '?')})"
                )

            chain.steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    operation="traverse",
                    description=f"Path {i + 1} ({path_length} hops):",
                    evidence=step_desc_parts,
                    confidence=self._scorer.path_confidence(
                        ConfidenceSignals(shortest_path_length=path_length)
                    ),
                )
            )

        best = results[0]
        nodes = best.get("path_nodes", [])
        if len(nodes) >= 2:
            chain.conclusion = (
                f"Connection found: {nodes[0].get('name')} connects to "
                f"{nodes[-1].get('name')} through {len(nodes) - 2} "
                f"intermediate node(s) via "
                f"{best.get('path_length')} relationship(s)."
            )

        chain.source_count = len(results)
        chain.evidence_summary = (
            f"Found {len(results)} path(s) between entities. "
            f"Shortest path: {results[0].get('path_length', '?')} hops."
        )
        return chain

    # ── Aggregation ──────────────────────────────────────────────────

    def _build_aggregation_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="aggregation")
        chain.source_count = len(results)
        for i, r in enumerate(results):
            chain.steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    operation="aggregate",
                    description="Aggregated data point.",
                    evidence=[f"{k}: {v}" for k, v in r.items()],
                    confidence=self._scorer.step_confidence(r),
                )
            )
        chain.conclusion = f"Aggregated {len(results)} results."
        return chain

    # ── Temporal ─────────────────────────────────────────────────────

    def _build_temporal_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="temporal")

        if not results:
            chain.conclusion = (
                "No activity found in the specified time period."
            )
            return chain

        chain.source_count = len(results)

        topic_groups: dict[str, list[dict]] = {}
        for doc in results:
            doc_data = doc.get("document", doc)
            topics = doc_data.get("topics", ["uncategorized"])
            for topic in topics:
                topic_groups.setdefault(topic, []).append(doc_data)

        step_num = 1
        for topic, docs in sorted(
            topic_groups.items(), key=lambda x: len(x[1]), reverse=True
        ):
            chain.steps.append(
                ReasoningStep(
                    step_number=step_num,
                    operation="aggregate",
                    description=f"Topic '{topic}': {len(docs)} document(s)",
                    evidence=[
                        f"'{d.get('title', '?')}' "
                        f"(modified: {d.get('modified_at', '?')})"
                        for d in docs[:5]
                    ],
                    confidence=self._scorer.step_confidence(
                        docs[0] if docs else {},
                        expected_keys=["title", "modified_at"],
                    ),
                )
            )
            step_num += 1

        most_active = max(topic_groups, key=lambda k: len(topic_groups[k]))
        chain.conclusion = (
            f"During this period, you worked on {len(topic_groups)} "
            f"topic area(s) across {len(results)} document(s). "
            f"Most active topic: '{most_active}'"
        )
        chain.evidence_summary = (
            f"Analyzed {len(results)} documents from the specified "
            f"time range."
        )
        return chain

    # ── Comparison ───────────────────────────────────────────────────

    def _build_comparison_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="comparison")

        if len(results) < 2:
            chain.conclusion = "Not enough data for comparison."
            return chain

        chain.source_count = len(results)

        for i, item in enumerate(results):
            chain.steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    operation="aggregate",
                    description=(
                        f"Entity: "
                        f"{item.get('topic', item.get('entity', '?'))}"
                    ),
                    evidence=[f"{k}: {v}" for k, v in item.items() if v],
                    confidence=self._scorer.step_confidence(item),
                )
            )

        comparisons: list[str] = []
        numeric_keys = [
            k
            for k in results[0]
            if isinstance(results[0].get(k), (int, float))
        ]
        for key in numeric_keys:
            values = [
                (
                    r.get("topic", r.get("entity", "?")),
                    r.get(key, 0),
                )
                for r in results
            ]
            winner = max(values, key=lambda x: x[1] if x[1] else 0)
            comparisons.append(f"{key}: {winner[0]} leads ({winner[1]})")

        chain.conclusion = "Comparison: " + "; ".join(comparisons)
        return chain

    # ── Causal ───────────────────────────────────────────────────────

    def _build_causal_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="causal")
        chain.source_count = len(results)
        for i, r in enumerate(results):
            chain.steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    operation="infer",
                    description="Temporal/causal data point.",
                    evidence=[f"{k}: {v}" for k, v in r.items() if v],
                    confidence=self._scorer.step_confidence(r),
                )
            )
        chain.conclusion = (
            f"Traced causal chain across {len(results)} events/documents."
        )
        return chain

    # ── Exploration ──────────────────────────────────────────────────

    def _build_exploration_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="exploration")
        chain.source_count = len(results)

        by_rel: dict[str, list[dict]] = {}
        for r in results:
            rel = r.get("rel_type", "unknown")
            by_rel.setdefault(rel, []).append(r)

        step_num = 1
        for rel_type, items in by_rel.items():
            chain.steps.append(
                ReasoningStep(
                    step_number=step_num,
                    operation="traverse",
                    description=(
                        f"Relationship '{rel_type}': "
                        f"{len(items)} connections"
                    ),
                    evidence=[
                        f"{item.get('direction', '?')} → "
                        f"{item.get('node_name', '?')} "
                        f"({item.get('node_type', '?')})"
                        for item in items[:5]
                    ],
                    confidence=self._scorer.step_confidence(
                        items[0] if items else {},
                        expected_keys=["direction", "node_name", "node_type"],
                    ),
                )
            )
            step_num += 1

        chain.conclusion = (
            f"Found {len(results)} connections across "
            f"{len(by_rel)} relationship types."
        )
        return chain

    # ── Generic / fallback ───────────────────────────────────────────

    def _build_generic_chain(
        self, query: str, results: list[dict]
    ) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="generic")
        chain.source_count = len(results)
        for i, r in enumerate(results[:10]):
            chain.steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    operation="lookup",
                    description="Result.",
                    evidence=[f"{k}: {v}" for k, v in r.items() if v],
                    confidence=self._scorer.step_confidence(r),
                )
            )
        chain.conclusion = f"Found {len(results)} results."
        return chain

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _summarize_entity(entity: dict) -> str:
        parts: list[str] = []
        for k, v in entity.items():
            if v and v != []:
                if isinstance(v, list):
                    parts.append(
                        f"{k}: {', '.join(str(x) for x in v)}"
                    )
                else:
                    parts.append(f"{k}: {v}")
        return "; ".join(parts[:6])

    @staticmethod
    def _measure_completeness(results: list[dict]) -> float:
        """Fraction of non-empty values across all result records."""
        if not results:
            return 0.0
        total = 0
        filled = 0
        for r in results:
            for v in r.values():
                total += 1
                if v is not None and v != "" and v != []:
                    filled += 1
        return filled / max(total, 1)
