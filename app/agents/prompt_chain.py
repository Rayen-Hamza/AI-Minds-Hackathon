"""
Prompt Chaining Pipeline using Google ADK.

Flow:
1. User query → Ontological Reasoning (Neo4j graph traversal)
2. Enriched query → Qdrant semantic search (RAG)
3. Reasoning + RAG → Context-limited prompt for small LLM

Designed for sub-4B parameter models with ~2K token context limits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.models import LiteLlm

from ..config import settings
from ..services.storage import get_qdrant_manager
from ..services.neo4j import get_driver
from ..services.graph_reasoning import GraphReasoningOrchestrator

logger = logging.getLogger(__name__)

# ============================================================================
# Context Limits for Small LLMs
# ============================================================================

# Token budget allocation (total ~1500 tokens for small LLM)
MAX_REASONING_TOKENS = 400  # Ontological reasoning summary
MAX_RAG_TOKENS = 600  # Qdrant retrieval context
MAX_QUERY_TOKENS = 100  # User query + instructions
RESERVE_TOKENS = 400  # Leave room for LLM response

# Approximate chars per token (conservative estimate)
CHARS_PER_TOKEN = 4


@dataclass
class ChainContext:
    """Shared context passed through the prompt chain."""

    user_query: str
    ontological_reasoning: str = ""
    rag_results: list[str] = field(default_factory=list)
    enriched_query: str = ""
    final_prompt: str = ""
    confidence: float = 0.0
    source_count: int = 0


# ============================================================================
# Context Truncation Utilities
# ============================================================================


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately fit within token limit."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text

    # Smart truncation: try to end at sentence boundary
    truncated = text[:max_chars]
    last_period = truncated.rfind(".")
    last_newline = truncated.rfind("\n")

    # Find best break point
    break_point = max(last_period, last_newline)
    if break_point > max_chars * 0.7:  # Only use if not too short
        return truncated[: break_point + 1] + "..."

    return truncated + "..."


def truncate_rag_results(results: list[str], max_tokens: int) -> list[str]:
    """Truncate RAG results to fit within token budget."""
    if not results:
        return []

    # Allocate tokens per result (with some overhead for formatting)
    tokens_per_result = max_tokens // min(len(results), 5)
    chars_per_result = tokens_per_result * CHARS_PER_TOKEN

    truncated = []
    total_chars = 0
    max_chars = max_tokens * CHARS_PER_TOKEN

    for result in results[:5]:  # Max 5 results
        if total_chars >= max_chars:
            break

        if len(result) > chars_per_result:
            result = result[:chars_per_result] + "..."

        truncated.append(result)
        total_chars += len(result)

    return truncated


# ============================================================================
# Chain Step 1: Ontological Reasoning
# ============================================================================


def enrich_with_ontology(user_query: str) -> dict:
    """
    Enrich user query with ontological reasoning from Neo4j knowledge graph.

    This step:
    - Extracts entities from the query
    - Resolves them in the knowledge graph
    - Retrieves relationships and context
    - Builds a reasoning chain

    Args:
        user_query: The original user question

    Returns:
        Dictionary with reasoning results and enriched context
    """
    try:
        driver = get_driver()
        if driver is None:
            logger.warning("Neo4j not connected, skipping ontological reasoning")
            return {
                "success": False,
                "user_query": user_query,
                "reasoning": "",
                "enriched_query": user_query,
                "confidence": 0.0,
                "entities": [],
            }

        # Use the GraphReasoningOrchestrator for ontological reasoning
        orchestrator = GraphReasoningOrchestrator(driver)

        # Warm up entity cache
        try:
            orchestrator.warm_up()
        except Exception as e:
            logger.debug(f"Entity cache warm-up failed: {e}")

        # Process through the reasoning pipeline
        # This extracts entities, resolves them, runs Cypher, builds reasoning chain
        reasoning_prompt = orchestrator.process_query(user_query)

        # Extract key information from the reasoning
        decomposed = orchestrator.decomposer.decompose(user_query)

        # Build enriched query with entity context
        entity_context = ""
        if decomposed.entities:
            entity_context = f" (entities: {', '.join(decomposed.entities)})"

        enriched_query = f"{user_query}{entity_context}"

        # Truncate reasoning to fit context limit
        truncated_reasoning = truncate_to_tokens(
            reasoning_prompt, MAX_REASONING_TOKENS
        )

        return {
            "success": True,
            "user_query": user_query,
            "reasoning": truncated_reasoning,
            "enriched_query": enriched_query,
            "confidence": decomposed.confidence,
            "entities": decomposed.entities,
            "reasoning_type": decomposed.reasoning_type.value,
        }

    except Exception as e:
        logger.error(f"Error in ontological reasoning: {e}")
        return {
            "success": False,
            "user_query": user_query,
            "reasoning": "",
            "enriched_query": user_query,
            "confidence": 0.0,
            "error": str(e),
        }


# ============================================================================
# Chain Step 2: Qdrant RAG Search
# ============================================================================


def search_qdrant_rag(enriched_query: str, limit: int = 5) -> dict:
    """
    Perform semantic search in Qdrant using the enriched query.

    This step:
    - Embeds the enriched query (includes entity context)
    - Searches across all modalities (text, image captions, audio transcripts)
    - Returns relevant context chunks

    Args:
        enriched_query: Query enriched with ontological context
        limit: Maximum number of results

    Returns:
        Dictionary with RAG search results
    """
    try:
        qdrant_manager = get_qdrant_manager()

        # Search unified collection (all modalities in same embedding space)
        results = qdrant_manager.search_unified(
            query_text=enriched_query,
            limit=limit,
            score_threshold=0.3,  # Filter low-relevance results
        )

        if not results:
            return {
                "success": True,
                "query": enriched_query,
                "results": [],
                "result_count": 0,
                "source_files": [],
            }

        # Extract text content and file paths from results
        rag_texts = []
        source_files = []
        for r in results:
            content = r.payload.chunk_text or ""
            source = r.payload.source_path or "unknown"
            content_type = r.payload.content_type or "text"
            score = r.score

            # Collect unique source file paths
            if source and source not in source_files:
                source_files.append(source)

            # Format as structured context (include source for traceability)
            formatted = f"[{content_type}:{score:.2f}|{source}] {content}"
            rag_texts.append(formatted)

        # Truncate to fit context limit
        truncated_results = truncate_rag_results(rag_texts, MAX_RAG_TOKENS)

        return {
            "success": True,
            "query": enriched_query,
            "results": truncated_results,
            "result_count": len(results),
            "truncated_count": len(truncated_results),
            "source_files": source_files,
        }

    except Exception as e:
        logger.error(f"Error in Qdrant RAG search: {e}")
        return {
            "success": False,
            "query": enriched_query,
            "results": [],
            "error": str(e),
        }


# ============================================================================
# Chain Step 3: Build Final Prompt
# ============================================================================


def build_context_limited_prompt(
    user_query: str,
    ontological_reasoning: str,
    rag_results: list[str],
    confidence: float = 0.0,
) -> dict:
    """
    Combine ontological reasoning and RAG results into a context-limited prompt.

    This step:
    - Merges reasoning chain with retrieved context
    - Ensures total prompt fits small LLM context window
    - Structures output for zero-reasoning narration

    Args:
        user_query: Original user question
        ontological_reasoning: Reasoning chain from graph
        rag_results: Retrieved context from Qdrant
        confidence: Pipeline confidence score

    Returns:
        Dictionary with the final LLM-ready prompt
    """
    try:
        # System prompt (optimized for small LLMs)
        system = (
            "You are a knowledge assistant. NARRATE the pre-computed answer.\n"
            "RULES:\n"
            "1. ONLY use information from REASONING and CONTEXT below.\n"
            "2. Do NOT add information not present.\n"
            "3. If confidence < 50%, say \"I'm not fully certain, but...\"\n"
            "4. Keep responses concise (2-5 sentences).\n"
            "5. Use bullet points for lists."
        )

        # Build context sections
        sections = []

        # Add ontological reasoning if available
        if ontological_reasoning:
            sections.append(f"REASONING:\n{ontological_reasoning}")

        # Add RAG context if available
        if rag_results:
            rag_block = "\n".join(f"• {r}" for r in rag_results)
            sections.append(f"CONTEXT:\n{rag_block}")

        # Combine sections
        context_block = "\n\n".join(sections) if sections else "No context available."

        # Build final prompt
        confidence_pct = int(confidence * 100)
        final_prompt = (
            f"{system}\n\n"
            f"---\n"
            f"CONFIDENCE: {confidence_pct}%\n\n"
            f"{context_block}\n"
            f"---\n\n"
            f"QUESTION: {user_query}\n\n"
            f"ANSWER:"
        )

        # Verify total length is within limits
        total_tokens = len(final_prompt) // CHARS_PER_TOKEN
        max_total = MAX_REASONING_TOKENS + MAX_RAG_TOKENS + MAX_QUERY_TOKENS

        if total_tokens > max_total:
            logger.warning(
                f"Prompt exceeds target ({total_tokens} > {max_total} tokens), truncating"
            )
            # Emergency truncation of context block
            excess_chars = (total_tokens - max_total) * CHARS_PER_TOKEN
            context_block = context_block[:-excess_chars] + "..."
            final_prompt = (
                f"{system}\n\n"
                f"---\n"
                f"CONFIDENCE: {confidence_pct}%\n\n"
                f"{context_block}\n"
                f"---\n\n"
                f"QUESTION: {user_query}\n\n"
                f"ANSWER:"
            )

        return {
            "success": True,
            "prompt": final_prompt,
            "token_estimate": len(final_prompt) // CHARS_PER_TOKEN,
            "has_reasoning": bool(ontological_reasoning),
            "has_rag": bool(rag_results),
            "confidence": confidence,
        }

    except Exception as e:
        logger.error(f"Error building final prompt: {e}")
        return {
            "success": False,
            "prompt": f"Question: {user_query}\n\nAnswer:",
            "error": str(e),
        }


# ============================================================================
# Full Chain Execution
# ============================================================================


def run_prompt_chain(user_query: str) -> dict:
    """
    Execute the full prompt chaining pipeline.

    Pipeline:
    1. Ontological reasoning (Neo4j graph traversal)
    2. RAG search (Qdrant semantic search)
    3. Prompt construction (context-limited)

    Args:
        user_query: The user's question

    Returns:
        Dictionary with the final prompt and metadata
    """
    try:
        logger.info(f"Running prompt chain for: {user_query[:50]}...")

        # Step 1: Ontological reasoning
        reasoning_result = enrich_with_ontology(user_query)
        ontological_reasoning = reasoning_result.get("reasoning", "")
        enriched_query = reasoning_result.get("enriched_query", user_query)
        confidence = reasoning_result.get("confidence", 0.0)

        logger.debug(
            f"Ontological step: success={reasoning_result.get('success')}, "
            f"entities={reasoning_result.get('entities', [])}"
        )

        # Step 2: RAG search with enriched query
        rag_result = search_qdrant_rag(enriched_query, limit=5)
        rag_results = rag_result.get("results", [])

        logger.debug(
            f"RAG step: success={rag_result.get('success')}, "
            f"results={rag_result.get('result_count', 0)}"
        )

        # Step 3: Build context-limited prompt
        prompt_result = build_context_limited_prompt(
            user_query=user_query,
            ontological_reasoning=ontological_reasoning,
            rag_results=rag_results,
            confidence=confidence,
        )

        logger.info(
            f"Prompt chain complete: tokens≈{prompt_result.get('token_estimate', 0)}, "
            f"reasoning={prompt_result.get('has_reasoning')}, "
            f"rag={prompt_result.get('has_rag')}"
        )

        return {
            "success": True,
            "user_query": user_query,
            "final_prompt": prompt_result.get("prompt", ""),
            "token_estimate": prompt_result.get("token_estimate", 0),
            "has_reasoning": prompt_result.get("has_reasoning", False),
            "has_rag": prompt_result.get("has_rag", False),
            "confidence": confidence,
            "entities_found": reasoning_result.get("entities", []),
            "rag_results_count": rag_result.get("result_count", 0),
            "source_files": rag_result.get("source_files", []),
        }

    except Exception as e:
        logger.error(f"Error in prompt chain: {e}")
        return {
            "success": False,
            "user_query": user_query,
            "final_prompt": f"Question: {user_query}\n\nAnswer:",
            "error": str(e),
            "source_files": [],
        }


# ============================================================================
# Google ADK Sequential Agent for Prompt Chaining
# ============================================================================

# Individual step agents for the chain

ontology_agent = Agent(
    name="ontology_enricher",
    model=LiteLlm(
        model=f"openai/{settings.llm_model}",
        api_base=settings.llm_base_url,
        api_key="dummy",
    ),
    description="Enriches queries with ontological reasoning from the knowledge graph.",
    instruction="""You extract entities and relationships from user queries.
Use the enrich_with_ontology tool to get graph-based reasoning.""",
    tools=[FunctionTool(func=enrich_with_ontology)],
)

rag_agent = Agent(
    name="rag_searcher",
    model=LiteLlm(
        model=f"openai/{settings.llm_model}",
        api_base=settings.llm_base_url,
        api_key="dummy",
    ),
    description="Searches Qdrant for relevant context using enriched queries.",
    instruction="""You search the vector database for relevant information.
Use the search_qdrant_rag tool with the enriched query.""",
    tools=[FunctionTool(func=search_qdrant_rag)],
)

prompt_builder_agent = Agent(
    name="prompt_builder",
    model=LiteLlm(
        model=f"openai/{settings.llm_model}",
        api_base=settings.llm_base_url,
        api_key="dummy",
    ),
    description="Builds context-limited prompts from reasoning and RAG results.",
    instruction="""You combine reasoning and context into a final prompt.
Use the build_context_limited_prompt tool.""",
    tools=[FunctionTool(func=build_context_limited_prompt)],
)

# Full chain agent (exposes the complete pipeline as a single tool)
chain_agent = Agent(
    name="prompt_chain_agent",
    model=LiteLlm(
        model=f"openai/{settings.llm_model}",
        api_base=settings.llm_base_url,
        api_key="dummy",
    ),
    description="""Prompt chaining agent that enriches queries with ontological reasoning,
retrieves RAG context from Qdrant, and builds context-limited prompts for small LLMs.""",
    instruction="""You run the full prompt chaining pipeline:
1. Enrich query with ontological reasoning (Neo4j knowledge graph)
2. Search Qdrant for relevant context (RAG)
3. Build a context-limited prompt that fits small LLM limits

Use the run_prompt_chain tool to execute the full pipeline.""",
    tools=[FunctionTool(func=run_prompt_chain)],
)
