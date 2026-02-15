"""Reasoning Chain Builder integration test with sample-doc scenarios.

Simulates the full decompose → route → (mock Cypher results) → build_chain →
prompt_builder pipeline using realistic data derived from
``sample_onthological_relation1.txt`` and ``sample_onthological_relation2.txt``.

The LLM is never called — we assume it would call the right Cypher template.
We feed **simulated Neo4j results** that match what the graph would return if
the sample docs were fully ingested.

Outputs:
  ``tests/reasoning_chain_results.md`` — human-readable dump of every
  query's chain context (i.e. exactly what would be injected into the
  LLM prompt).  A human reviewer reads this to judge chain quality.

Run with:
    pytest tests/test_reasoning_chains.py -v --tb=short -s
"""

from __future__ import annotations

import pathlib
import textwrap
from dataclasses import dataclass
from datetime import datetime

import pytest

from app.models.reasoning import ReasoningChain, ReasoningStep, ReasoningType
from app.services.query_decomposer import QueryDecomposer
from app.services.reasoning_chain_builder import ReasoningChainBuilder
from app.services.prompt_builder import PromptBuilder
from app.services.template_router import TemplateRouter

# ── Paths ────────────────────────────────────────────────────────────

TESTS_DIR = pathlib.Path(__file__).parent
OUTPUT_MD = TESTS_DIR / "reasoning_chain_results.md"

# ── Simulated Neo4j result payloads ──────────────────────────────────
# Each key maps to what a specific Cypher template's RETURN clause would
# produce when executed against a graph built from the two sample docs.
# Shape must match the template's RETURN exactly:
#
#   entity_lookup_person  → {canonical_name, email, role, mention_count,
#                            organizations:[], expertise:[], projects:[]}
#   entity_lookup_topic   → {name, description, mention_count,
#                            importance_score, document_count,
#                            related_topics:[], parent_topic,
#                            subtopics:[]}
#   person_connections    → {person, connections:[{name, relationship,
#                            strength}], projects:[], organizations:[],
#                            events:[{name, date}]}
#   full_neighborhood     → {rel_type, direction, node_type, node_name,
#                            rel_props:{}}
#   shortest_path_entities→ {path_nodes:[{type, name}],
#                            path_relationships:[str],
#                            path_length:int}
#   count_by_topic        → {topic, document_count, sample_documents:[]}
#   top_entities_by_mentions → {entity, mentions, type}
#   documents_in_timerange→ {document: {title, file_path, modified_at,
#                            summary, topics:[], project}}
#   compare_topics        → {topic, mentions, importance, document_count,
#                            related_topics:[]}
#   temporal_chain        → {title, created_at, summary}
#
# Data is sourced from the ground-truth sections of
# sample_onthological_relation1.txt / sample_onthological_relation2.txt.

NEO4J_SIM: dict[str, list[dict]] = {

    # ═══════════════════════════════════════════════════════════════════
    # ENTITY LOOKUP — Person  (template: entity_lookup_person)
    # ═══════════════════════════════════════════════════════════════════

    "person:sarah_chen": [
        {
            "canonical_name": "Sarah Chen",
            "email": "s.chen@nexus.tech",
            "role": "Meeting Chair / Keynote Speaker",
            "mention_count": 5,
            "organizations": ["Nexus Technologies"],
            "expertise": ["AI Platform Strategy"],
            "projects": ["Project Atlas"],
        }
    ],
    "person:marcus_rivera": [
        {
            "canonical_name": "Marcus Rivera",
            "email": "m.rivera@nexus.tech",
            "role": "ML Engineer — Foundation Models sub-team lead",
            "mention_count": 6,
            "organizations": ["Nexus Technologies"],
            "expertise": [
                "PyTorch", "TensorFlow", "mixture-of-experts",
                "dense transformer",
            ],
            "projects": ["Project Atlas", "Foundation Models"],
        }
    ],
    "person:priya_kapoor": [
        {
            "canonical_name": "Priya Kapoor",
            "email": "p.kapoor@nexus.tech",
            "role": "Competitive Intelligence / Compliance Analyst",
            "mention_count": 4,
            "organizations": ["Nexus Technologies"],
            "expertise": ["ONNX", "EU AI Act", "competitive analysis"],
            "projects": ["Project Atlas"],
        }
    ],
    "person:david_okonkwo": [
        {
            "canonical_name": "David Okonkwo",
            "email": "d.okonkwo@nexus.tech",
            "role": "Infrastructure Lead",
            "mention_count": 4,
            "organizations": ["Nexus Technologies"],
            "expertise": ["Hermes API", "infrastructure"],
            "projects": ["Project Atlas", "Hermes API"],
        }
    ],
    "person:lena_vasquez": [
        {
            "canonical_name": "Lena Vasquez",
            "email": "l.vasquez@nexus.tech",
            "role": "Research Lead / Author",
            "mention_count": 4,
            "organizations": ["Nexus Technologies"],
            "expertise": ["SFT", "pre-training", "distributed training"],
            "projects": ["Meridian-7B", "Meridian-7B-SFT"],
        }
    ],
    "person:elena_rossi": [
        {
            "canonical_name": "Professor Elena Rossi",
            "email": "e.rossi@ed.ac.uk",
            "role": "Academic Advisor — AI Safety",
            "mention_count": 4,
            "organizations": ["University of Edinburgh"],
            "expertise": [
                "Constitutional AI", "toxicity filtering",
                "two-pass filtering", "AI Safety",
            ],
            "projects": ["Meridian-7B"],
        }
    ],
    "person:tomas_herrera": [
        {
            "canonical_name": "Tomás Herrera",
            "email": "t.herrera@nexus.tech",
            "role": "Safety / DPO Engineer",
            "mention_count": 5,
            "organizations": ["Nexus Technologies"],
            "expertise": [
                "DPO", "toxicity classifier", "TRL library",
                "RedPajama-v2",
            ],
            "projects": ["Meridian-7B", "Meridian-7B-Chat"],
        }
    ],
    "person:yuki_tanaka": [
        {
            "canonical_name": "Yuki Tanaka",
            "email": "y.tanaka@nexus.tech",
            "role": "Evaluation Lead",
            "mention_count": 4,
            "organizations": ["Nexus Technologies"],
            "expertise": [
                "HellaSwag", "MMLU", "GGUF quantization",
                "LM Evaluation Harness",
            ],
            "projects": ["Meridian-7B"],
        }
    ],

    # ═══════════════════════════════════════════════════════════════════
    # ENTITY LOOKUP — Topic  (template: entity_lookup_topic)
    # ═══════════════════════════════════════════════════════════════════

    "topic:project_atlas": [
        {
            "name": "Project Atlas",
            "description": (
                "Core AI inference engine. Migrated from TensorFlow to "
                "PyTorch, reducing latency from 120ms to 68ms. ONNX "
                "export pipeline in staging at Berlin datacenter."
            ),
            "mention_count": 7,
            "importance_score": 0.82,
            "document_count": 1,
            "related_topics": [
                "PyTorch", "TensorFlow", "ONNX",
                "mixture-of-experts", "EU AI Act",
            ],
            "parent_topic": None,
            "subtopics": ["Atlas v2.3", "Hermes API"],
        }
    ],
    "topic:pytorch": [
        {
            "name": "PyTorch",
            "description": (
                "Deep-learning framework. Project Atlas migrated to "
                "PyTorch from TensorFlow."
            ),
            "mention_count": 3,
            "importance_score": 0.65,
            "document_count": 2,
            "related_topics": [
                "TensorFlow", "Project Atlas", "ONNX",
                "DeepSpeed ZeRO",
            ],
            "parent_topic": None,
            "subtopics": [],
        }
    ],
    "topic:meridian": [
        {
            "name": "Meridian-7B",
            "description": (
                "7-billion-parameter LLM pre-trained on 128 × H100 "
                "GPUs on the Condor cluster.  Dataset: RedPajama-v2 + "
                "The Stack v2 + OpenWebMath + AMPS + Wikipedia + "
                "BookCorpus.  Pre-training cost: $312,000 on CoreWeave."
            ),
            "mention_count": 12,
            "importance_score": 0.91,
            "document_count": 1,
            "related_topics": [
                "DeepSpeed ZeRO", "RedPajama-v2", "DPO", "SFT",
                "Constitutional AI", "GGUF quantization",
                "TruthfulQA", "HellaSwag", "MMLU",
            ],
            "parent_topic": None,
            "subtopics": ["Meridian-7B-SFT", "Meridian-7B-Chat"],
        }
    ],
    "topic:dpo": [
        {
            "name": "DPO (Direct Preference Optimization)",
            "description": (
                "Post-training alignment technique used on Meridian-7B-"
                "SFT.  48,200 preference pairs from Scale AI (Lisa "
                "Nguyen).  Trained by Tomás Herrera with TRL library "
                "from Hugging Face.  β ∈ {0.1, 0.3, 0.5}."
            ),
            "mention_count": 5,
            "importance_score": 0.60,
            "document_count": 1,
            "related_topics": [
                "SFT", "Constitutional AI", "TRL library",
                "Scale AI", "Meridian-7B-Chat",
            ],
            "parent_topic": None,
            "subtopics": [],
        }
    ],
    "topic:constitutional_ai": [
        {
            "name": "Constitutional AI",
            "description": (
                "Safety-alignment methodology.  Professor Elena Rossi "
                "(University of Edinburgh) consults on red-teaming-then-"
                "revise loop with ≥3 diverse evaluator personas."
            ),
            "mention_count": 3,
            "importance_score": 0.55,
            "document_count": 2,
            "related_topics": [
                "DPO", "AI Safety", "toxicity filtering",
                "two-pass filtering",
            ],
            "parent_topic": "AI Safety",
            "subtopics": [],
        }
    ],

    # ═══════════════════════════════════════════════════════════════════
    # RELATIONSHIP — Person connections  (template: person_connections)
    # ═══════════════════════════════════════════════════════════════════

    "rel:marcus_connections": [
        {
            "person": "Marcus Rivera",
            "connections": [
                {"name": "Sarah Chen", "relationship": "KNOWS", "strength": 0.92},
                {"name": "Priya Kapoor", "relationship": "KNOWS", "strength": 0.85},
                {"name": "David Okonkwo", "relationship": "KNOWS", "strength": 0.80},
                {"name": "Emily Zhang", "relationship": "KNOWS", "strength": 0.78},
                {"name": "James Thornton", "relationship": "KNOWS", "strength": 0.45},
            ],
            "projects": ["Project Atlas", "Foundation Models"],
            "organizations": ["Nexus Technologies"],
            "events": [
                {"name": "Barcelona Offsite", "date": "2026-02-10"},
                {"name": "Atlas v2.3 demo day", "date": "2026-04-05"},
            ],
        }
    ],
    "rel:lena_connections": [
        {
            "person": "Lena Vasquez",
            "connections": [
                {"name": "Tomás Herrera", "relationship": "KNOWS", "strength": 0.90},
                {"name": "Yuki Tanaka", "relationship": "KNOWS", "strength": 0.85},
                {"name": "Carlos Mendez", "relationship": "KNOWS", "strength": 0.80},
                {"name": "Amara Osei", "relationship": "KNOWS", "strength": 0.75},
                {"name": "Professor Elena Rossi", "relationship": "KNOWS", "strength": 0.60},
                {"name": "Fatima Al-Rashidi", "relationship": "KNOWS", "strength": 0.55},
            ],
            "projects": ["Meridian-7B", "Meridian-7B-SFT"],
            "organizations": ["Nexus Technologies"],
            "events": [],
        }
    ],

    # ═══════════════════════════════════════════════════════════════════
    # EXPLORATION — full_neighborhood
    # ═══════════════════════════════════════════════════════════════════

    "explore:meridian": [
        # incoming ABOUT — documents
        {"rel_type": "ABOUT", "direction": "incoming", "node_type": "Document",
         "node_name": "Research Log — Distributed Training Incident & Recovery",
         "rel_props": {"relevance_score": 0.98}},
        # outgoing RELATED_TO — topics
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "DeepSpeed ZeRO", "rel_props": {"strength": 0.85}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "RedPajama-v2", "rel_props": {"strength": 0.90}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "DPO", "rel_props": {"strength": 0.70}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "SFT", "rel_props": {"strength": 0.75}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "Constitutional AI", "rel_props": {"strength": 0.50}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "GGUF quantization", "rel_props": {"strength": 0.55}},
        # incoming SUBTOPIC_OF — sub-projects
        {"rel_type": "SUBTOPIC_OF", "direction": "incoming", "node_type": "Project",
         "node_name": "Meridian-7B-SFT", "rel_props": {}},
        {"rel_type": "SUBTOPIC_OF", "direction": "incoming", "node_type": "Project",
         "node_name": "Meridian-7B-Chat", "rel_props": {}},
        # incoming WORKED_ON — people
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "Lena Vasquez", "rel_props": {}},
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "Tomás Herrera", "rel_props": {}},
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "Yuki Tanaka", "rel_props": {}},
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "Carlos Mendez", "rel_props": {}},
    ],
    "explore:project_atlas": [
        {"rel_type": "ABOUT", "direction": "incoming", "node_type": "Document",
         "node_name": "Meeting Notes — Q1 2026 AI Platform Strategy",
         "rel_props": {"relevance_score": 0.95}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "PyTorch", "rel_props": {"strength": 0.90}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "TensorFlow", "rel_props": {"strength": 0.85}},
        {"rel_type": "RELATED_TO", "direction": "outgoing", "node_type": "Topic",
         "node_name": "ONNX", "rel_props": {"strength": 0.70}},
        {"rel_type": "SUBTOPIC_OF", "direction": "incoming", "node_type": "Project",
         "node_name": "Atlas v2.3", "rel_props": {}},
        {"rel_type": "SUBTOPIC_OF", "direction": "incoming", "node_type": "Project",
         "node_name": "Hermes API", "rel_props": {}},
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "Marcus Rivera", "rel_props": {}},
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "David Okonkwo", "rel_props": {}},
        {"rel_type": "WORKED_ON", "direction": "incoming", "node_type": "Person",
         "node_name": "Priya Kapoor", "rel_props": {}},
        {"rel_type": "FLAGGED_IN", "direction": "incoming", "node_type": "Topic",
         "node_name": "EU AI Act", "rel_props": {}},
    ],

    # ═══════════════════════════════════════════════════════════════════
    # MULTI-HOP — shortest_path_entities
    # ═══════════════════════════════════════════════════════════════════

    "path:marcus_to_mit": [
        {
            "path_nodes": [
                {"name": "Marcus Rivera", "type": "Person"},
                {"name": "mixture-of-experts", "type": "Topic"},
                {"name": "James Thornton", "type": "Person"},
                {"name": "MIT CSAIL", "type": "Organization"},
            ],
            "path_relationships": [
                "EXPERT_IN", "EXPERT_IN", "AFFILIATED_WITH",
            ],
            "path_length": 3,
        }
    ],
    "path:fatima_to_constitutional_ai": [
        # Ground truth: Fatima→Instruct-v3 (WORKED_ON), Instruct-v3
        # trains SFT (TRAINED_WITH), SFT→DPO (RELATED_TO),
        # DPO→Constitutional AI (RELATED_TO) — 4 hops
        {
            "path_nodes": [
                {"name": "Fatima Al-Rashidi", "type": "Person"},
                {"name": "Nexus-Instruct-v3", "type": "Project"},
                {"name": "Meridian-7B-SFT", "type": "Project"},
                {"name": "DPO", "type": "Topic"},
                {"name": "Constitutional AI", "type": "Topic"},
            ],
            "path_relationships": [
                "WORKED_ON", "TRAINED_WITH", "RELATED_TO", "RELATED_TO",
            ],
            "path_length": 4,
        }
    ],
    "path:scale_ai_to_meridian_chat": [
        # Ground truth: Scale AI (Lisa Nguyen) delivered preference
        # pairs → used for DPO training → produced Meridian-7B-Chat
        {
            "path_nodes": [
                {"name": "Scale AI", "type": "Organization"},
                {"name": "Lisa Nguyen", "type": "Person"},
                {"name": "DPO", "type": "Topic"},
                {"name": "Meridian-7B-Chat", "type": "Project"},
            ],
            "path_relationships": [
                "AFFILIATED_WITH", "WORKED_ON", "PRODUCED",
            ],
            "path_length": 3,
        }
    ],
    "path:rossi_to_patent": [
        # Ground truth: Rossi→two-pass filtering (EXPERT_IN)→patent
        {
            "path_nodes": [
                {"name": "Professor Elena Rossi", "type": "Person"},
                {"name": "two-pass toxicity filtering", "type": "Topic"},
                {"name": "Patent PA-2025-0892", "type": "Concept"},
            ],
            "path_relationships": ["EXPERT_IN", "RESULTED_IN"],
            "path_length": 2,
        }
    ],
    "path:eu_ai_act_to_atlas": [
        # Ground truth: EU AI Act→AI Safety (RELATED_TO),
        # compliance flagged 3 risk areas in Atlas pipeline
        {
            "path_nodes": [
                {"name": "EU AI Act", "type": "Topic"},
                {"name": "AI Safety", "type": "Topic"},
                {"name": "Project Atlas", "type": "Project"},
            ],
            "path_relationships": ["RELATED_TO", "FLAGGED_IN"],
            "path_length": 2,
        }
    ],

    # ═══════════════════════════════════════════════════════════════════
    # AGGREGATION  (templates: count_by_topic, top_entities_by_mentions)
    # ═══════════════════════════════════════════════════════════════════

    "agg:count_atlas_docs": [
        {
            "topic": "Project Atlas",
            "document_count": 1,
            "sample_documents": [
                "Meeting Notes — Q1 2026 AI Platform Strategy",
            ],
        },
    ],
    "agg:top_people": [
        {"entity": "Marcus Rivera",  "mentions": 6, "type": "Person"},
        {"entity": "Sarah Chen",     "mentions": 5, "type": "Person"},
        {"entity": "Tomás Herrera",  "mentions": 5, "type": "Person"},
        {"entity": "Lena Vasquez",   "mentions": 4, "type": "Person"},
        {"entity": "Yuki Tanaka",    "mentions": 4, "type": "Person"},
        {"entity": "Priya Kapoor",   "mentions": 4, "type": "Person"},
        {"entity": "David Okonkwo",  "mentions": 4, "type": "Person"},
        {"entity": "Elena Rossi",    "mentions": 4, "type": "Person"},
        {"entity": "Carlos Mendez",  "mentions": 3, "type": "Person"},
        {"entity": "Amara Osei",     "mentions": 3, "type": "Person"},
    ],
    "agg:content_stats": [
        {"type": "Topics",    "cnt": 35},
        {"type": "People",    "cnt": 16},
        {"type": "Documents", "cnt": 2},
        {"type": "Projects",  "cnt": 7},
        {"type": "Concepts",  "cnt": 3},
    ],

    # ═══════════════════════════════════════════════════════════════════
    # TEMPORAL  (template: documents_in_timerange)
    # Result shape: {document: {title, file_path, modified_at, summary,
    #                topics:[], project}}
    # ═══════════════════════════════════════════════════════════════════

    "temporal:last_month": [
        {
            "document": {
                "title": "DPO training complete — Meridian-7B-Chat",
                "file_path": "/research/meridian/entry8_dpo_complete.md",
                "modified_at": "2025-12-19",
                "summary": (
                    "DPO training finished.  MT-Bench 7.8/10, "
                    "TruthfulQA 47.3%, safety eval 94.2% refusal."
                ),
                "topics": ["DPO", "Meridian-7B-Chat", "Constitutional AI"],
                "project": "Meridian-7B",
            }
        },
        {
            "document": {
                "title": "SFT training complete — Meridian-7B-SFT",
                "file_path": "/research/meridian/entry7_sft_complete.md",
                "modified_at": "2025-12-12",
                "summary": (
                    "SFT finished after 3 epochs.  MT-Bench 7.2/10. "
                    "List-bias found in Nexus-Instruct-v3 (34% bullet)."
                ),
                "topics": ["SFT", "Meridian-7B-SFT", "Nexus-Instruct-v3"],
                "project": "Meridian-7B",
            }
        },
        {
            "document": {
                "title": "SFT phase started — preference data collection",
                "file_path": "/research/meridian/entry6_sft_start.md",
                "modified_at": "2025-12-05",
                "summary": (
                    "SFT started on 32 GPUs.  OOM at batch 8 / "
                    "seq 4096, resolved with gradient accumulation + "
                    "Flash Attention 2.  Tomás contracted Scale AI "
                    "for 50k preference pairs."
                ),
                "topics": ["SFT", "Scale AI", "Flash Attention 2"],
                "project": "Meridian-7B",
            }
        },
    ],
    "temporal:training_timeline": [
        {
            "document": {
                "title": "Pre-training started on Condor cluster",
                "file_path": "/research/meridian/entry1_start.md",
                "modified_at": "2025-11-03",
                "summary": (
                    "128 × H100 GPUs, DeepSpeed ZeRO Stage 3. "
                    "Dataset: RedPajama-v2 filtered.  Estimated 14 "
                    "days, $380k on CoreWeave."
                ),
                "topics": [
                    "Meridian-7B", "DeepSpeed ZeRO",
                    "RedPajama-v2", "CoreWeave",
                ],
                "project": "Meridian-7B",
            }
        },
        {
            "document": {
                "title": "Data mix adjusted — MMLU underperforming",
                "file_path": "/research/meridian/entry2_datamix.md",
                "modified_at": "2025-11-07",
                "summary": (
                    "Yuki flagged low MMLU math scores.  New mix: "
                    "70% RedPajama-v2, 15% Stack v2, 10% OpenWebMath+"
                    "AMPS, 5% Wikipedia+BookCorpus.  Carlos approved."
                ),
                "topics": [
                    "MMLU", "RedPajama-v2", "OpenWebMath", "AMPS",
                ],
                "project": "Meridian-7B",
            }
        },
        {
            "document": {
                "title": "GPU failure — worker-gpu-089 ECC error",
                "file_path": "/research/meridian/entry3_incident.md",
                "modified_at": "2025-11-12",
                "summary": (
                    "ECC memory error at step 22,847.  Cooling fan "
                    "failure on worker-gpu-089 (87°C sustained).  "
                    "Rolled back to checkpoint 22,000; 847 steps / "
                    "$2,300 lost.  Amara Osei root-cause analysis."
                ),
                "topics": [
                    "Meridian-7B", "ECC memory error",
                    "Condor cluster", "CoreWeave",
                ],
                "project": "Meridian-7B",
            }
        },
        {
            "document": {
                "title": "50k-step milestone — TruthfulQA gap",
                "file_path": "/research/meridian/entry4_50k.md",
                "modified_at": "2025-11-19",
                "summary": (
                    "Pile ppl 8.4, HellaSwag 71.2%, MMLU 44.8%.  "
                    "TruthfulQA 34.2% vs Mistral 42.1%.  Rossi "
                    "recommended two-pass filtering."
                ),
                "topics": [
                    "TruthfulQA", "HellaSwag", "MMLU",
                    "Constitutional AI",
                ],
                "project": "Meridian-7B",
            }
        },
        {
            "document": {
                "title": "Pre-training complete — 87,500 steps",
                "file_path": "/research/meridian/entry5_done.md",
                "modified_at": "2025-11-28",
                "summary": (
                    "Final metrics: Pile ppl 6.8, HellaSwag 76.4%, "
                    "MMLU 51.2%, TruthfulQA 39.8%.  11.2 days, "
                    "$312k (under budget by $68k)."
                ),
                "topics": [
                    "Meridian-7B", "HellaSwag", "MMLU",
                    "TruthfulQA", "GGUF quantization",
                ],
                "project": "Meridian-7B",
            }
        },
    ],

    # ═══════════════════════════════════════════════════════════════════
    # COMPARISON  (template: compare_topics)
    # Result shape: {topic, mentions, importance, document_count,
    #                related_topics:[]}
    # ═══════════════════════════════════════════════════════════════════

    "compare:pytorch_tensorflow": [
        {
            "topic": "PyTorch",
            "mentions": 4,
            "importance": 0.65,
            "document_count": 2,
            "related_topics": [
                "TensorFlow", "Project Atlas", "ONNX",
                "DeepSpeed ZeRO",
            ],
        },
        {
            "topic": "TensorFlow",
            "mentions": 2,
            "importance": 0.40,
            "document_count": 1,
            "related_topics": ["PyTorch", "Project Atlas"],
        },
    ],
    "compare:dpo_sft": [
        {
            "topic": "DPO",
            "mentions": 5,
            "importance": 0.60,
            "document_count": 1,
            "related_topics": [
                "SFT", "Constitutional AI", "TRL library",
                "Scale AI",
            ],
        },
        {
            "topic": "SFT",
            "mentions": 4,
            "importance": 0.55,
            "document_count": 1,
            "related_topics": [
                "DPO", "Nexus-Instruct-v3",
                "Meridian-7B-SFT",
            ],
        },
    ],

    # ═══════════════════════════════════════════════════════════════════
    # CAUSAL  (template: temporal_chain)
    # Result shape: {title, created_at, summary}
    # Each list is an ordered causal sequence sourced from the ground-
    # truth CAUSAL CHAINS section of sample 2.
    # ═══════════════════════════════════════════════════════════════════

    "causal:gpu_failure": [
        {
            "title": "Elevated temperature on worker-gpu-089",
            "created_at": "2025-11-10",
            "summary": (
                "Condor health monitoring flagged sustained 87°C on "
                "worker-gpu-089.  Failing cooling fan assembly."
            ),
        },
        {
            "title": "ECC memory error at step 22,847",
            "created_at": "2025-11-12",
            "summary": (
                "GPU node threw ECC error.  DeepSpeed elastic training "
                "detected failure, redistributed to 127 GPUs."
            ),
        },
        {
            "title": "Optimizer state corruption on 3 data-parallel ranks",
            "created_at": "2025-11-12",
            "summary": (
                "Automatic recovery corrupted optimizer state for 3 of "
                "128 data-parallel ranks."
            ),
        },
        {
            "title": "Rollback to checkpoint step 22,000",
            "created_at": "2025-11-12",
            "summary": (
                "847 steps lost ≈ $2,300 compute waste.  Restarted "
                "training on 127 GPUs."
            ),
        },
        {
            "title": "Pre-emptive drain policy implemented",
            "created_at": "2025-11-19",
            "summary": (
                "Temperature-based drain when >82°C sustained for 30+ "
                "minutes.  Committed to Condor cluster config, "
                "GitHub PR #4521.  Replacement node worker-gpu-091 "
                "online."
            ),
        },
    ],
    "causal:truthfulqa": [
        {
            "title": "Aggressive safety filter on factual content",
            "created_at": "2025-11-19",
            "summary": (
                "Safety filter too aggressive on controversial-but-"
                "factual content, causing excessive hedging."
            ),
        },
        {
            "title": "Low TruthfulQA score — 34.2% vs Mistral 42.1%",
            "created_at": "2025-11-19",
            "summary": (
                "Meridian-7B scores 34.2% on TruthfulQA.  Mistral-7B-"
                "v0.1 scores 42.1%.  Gap attributed to safety filter."
            ),
        },
        {
            "title": "Professor Rossi consultation — two-pass filtering",
            "created_at": "2025-11-19",
            "summary": (
                "Elena Rossi (University of Edinburgh) recommended "
                "two-pass approach: first pass for genuine toxicity, "
                "second pass for factual calibration."
            ),
        },
        {
            "title": "TruthfulQA improved to 39.8% at pre-training end",
            "created_at": "2025-11-28",
            "summary": (
                "After filter adjustment, TruthfulQA rose from 34.2% "
                "to 39.8% at step 87,500 (pre-training completion)."
            ),
        },
        {
            "title": "Patent application PA-2025-0892 filed",
            "created_at": "2025-12-19",
            "summary": (
                "Two-pass toxicity filtering method developed with "
                "Professor Rossi.  Patent filed as PA-2025-0892."
            ),
        },
    ],
    "causal:list_bias": [
        {
            "title": "Nexus-Instruct-v3 dataset imbalance",
            "created_at": "2025-12-12",
            "summary": (
                "34% of Nexus-Instruct-v3 responses use bullet-point "
                "format, biasing the SFT model toward list generation."
            ),
        },
        {
            "title": "Meridian-7B-SFT generates lists inappropriately",
            "created_at": "2025-12-12",
            "summary": (
                "Yuki Tanaka discovered list bias: model produces "
                "bullets even when narrative answers are appropriate."
            ),
        },
        {
            "title": "Fatima Al-Rashidi rebalancing dataset for v4",
            "created_at": "2025-12-12",
            "summary": (
                "Toronto team rebalancing instruction dataset to "
                "reduce list format ratio.  Nexus-Instruct-v4 planned."
            ),
        },
    ],

    # ═══════════════════════════════════════════════════════════════════
    # EMPTY  — for graceful-degradation tests
    # ═══════════════════════════════════════════════════════════════════
    "empty": [],
}


# ── Query scenario definitions ───────────────────────────────────────

@dataclass
class QueryScenario:
    """A test query with its simulated graph results."""
    category: str          # "common" or "challenging"
    user_query: str
    sim_key: str           # key into NEO4J_SIM
    reasoning_type: ReasoningType
    description: str       # what this tests


COMMON_QUERIES: list[QueryScenario] = [
    QueryScenario(
        category="common",
        user_query="Who is Marcus Rivera?",
        sim_key="person:marcus_rivera",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Simple person lookup — most frequent query type",
    ),
    QueryScenario(
        category="common",
        user_query="Tell me about Project Atlas",
        sim_key="topic:project_atlas",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Topic lookup with subtopics (Atlas v2.3, Hermes API)",
    ),
    QueryScenario(
        category="common",
        user_query="What do I know about Meridian-7B?",
        sim_key="explore:meridian",
        reasoning_type=ReasoningType.EXPLORATION,
        description="Full-neighborhood exploration — groups by rel_type",
    ),
    QueryScenario(
        category="common",
        user_query="Who is Sarah Chen?",
        sim_key="person:sarah_chen",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Author lookup — role, org, projects",
    ),
    QueryScenario(
        category="common",
        user_query="What are the connections of Marcus Rivera?",
        sim_key="rel:marcus_connections",
        reasoning_type=ReasoningType.RELATIONSHIP,
        description="Relationship traversal — person_connections template",
    ),
    QueryScenario(
        category="common",
        user_query="What happened last month?",
        sim_key="temporal:last_month",
        reasoning_type=ReasoningType.TEMPORAL,
        description="Temporal — 3 documents across Dec 2025",
    ),
    QueryScenario(
        category="common",
        user_query="How many documents mention Project Atlas?",
        sim_key="agg:count_atlas_docs",
        reasoning_type=ReasoningType.AGGREGATION,
        description="Aggregation — count_by_topic template, 1 doc",
    ),
    QueryScenario(
        category="common",
        user_query="Who are the most mentioned people?",
        sim_key="agg:top_people",
        reasoning_type=ReasoningType.AGGREGATION,
        description="Aggregation — top 10 people by mention count",
    ),
    QueryScenario(
        category="common",
        user_query="Tell me about Professor Elena Rossi",
        sim_key="person:elena_rossi",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="External academic advisor — University of Edinburgh",
    ),
    QueryScenario(
        category="common",
        user_query="What is DPO?",
        sim_key="topic:dpo",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Technical-concept topic with rich description",
    ),
    QueryScenario(
        category="common",
        user_query="Who is Tomás Herrera?",
        sim_key="person:tomas_herrera",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Safety/DPO engineer across multiple projects",
    ),
    QueryScenario(
        category="common",
        user_query="What are the connections of Lena Vasquez?",
        sim_key="rel:lena_connections",
        reasoning_type=ReasoningType.RELATIONSHIP,
        description="Relationship traversal — research lead's network",
    ),
    QueryScenario(
        category="common",
        user_query="Tell me about Constitutional AI",
        sim_key="topic:constitutional_ai",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Topic with parent (AI Safety) and related topics",
    ),
]

CHALLENGING_QUERIES: list[QueryScenario] = [
    # ── Multi-hop ────────────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="How does Marcus Rivera connect to MIT CSAIL?",
        sim_key="path:marcus_to_mit",
        reasoning_type=ReasoningType.MULTI_HOP,
        description="3-hop: Marcus→MoE→Thornton→MIT CSAIL",
    ),
    QueryScenario(
        category="challenging",
        user_query="How does Fatima Al-Rashidi connect to Constitutional AI?",
        sim_key="path:fatima_to_constitutional_ai",
        reasoning_type=ReasoningType.MULTI_HOP,
        description="4-hop: Fatima→Instruct-v3→SFT→DPO→ConstitAI",
    ),
    QueryScenario(
        category="challenging",
        user_query="What is the relationship between Scale AI and Meridian-7B-Chat?",
        sim_key="path:scale_ai_to_meridian_chat",
        reasoning_type=ReasoningType.MULTI_HOP,
        description="3-hop: Scale AI→Lisa Nguyen→DPO→Meridian-7B-Chat",
    ),
    QueryScenario(
        category="challenging",
        user_query="How are Professor Rossi and patent PA-2025-0892 connected?",
        sim_key="path:rossi_to_patent",
        reasoning_type=ReasoningType.MULTI_HOP,
        description="2-hop causal: Rossi→two-pass filtering→patent",
    ),
    QueryScenario(
        category="challenging",
        user_query="What is the relationship between EU AI Act and Project Atlas?",
        sim_key="path:eu_ai_act_to_atlas",
        reasoning_type=ReasoningType.MULTI_HOP,
        description="2-hop: EU AI Act→AI Safety→Atlas (compliance)",
    ),
    # ── Causal ───────────────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="What caused the GPU failure incident?",
        sim_key="causal:gpu_failure",
        reasoning_type=ReasoningType.CAUSAL,
        description="5-step: temperature→ECC→corruption→rollback→policy",
    ),
    QueryScenario(
        category="challenging",
        user_query="What caused the TruthfulQA score to improve?",
        sim_key="causal:truthfulqa",
        reasoning_type=ReasoningType.CAUSAL,
        description="5-step: filter→low score→Rossi→fix→patent",
    ),
    QueryScenario(
        category="challenging",
        user_query="What caused the list bias in Meridian?",
        sim_key="causal:list_bias",
        reasoning_type=ReasoningType.CAUSAL,
        description="3-step: Instruct-v3 imbalance→model bias→rebalance",
    ),
    # ── Comparison ───────────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="Compare PyTorch and TensorFlow",
        sim_key="compare:pytorch_tensorflow",
        reasoning_type=ReasoningType.COMPARISON,
        description="Side-by-side: PyTorch leads in mentions & importance",
    ),
    QueryScenario(
        category="challenging",
        user_query="Compare DPO and SFT training approaches",
        sim_key="compare:dpo_sft",
        reasoning_type=ReasoningType.COMPARISON,
        description="Compare two training methodologies (close metrics)",
    ),
    # ── Exploration ──────────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="What is connected to Project Atlas?",
        sim_key="explore:project_atlas",
        reasoning_type=ReasoningType.EXPLORATION,
        description="Full neighborhood — people, topics, sub-projects, flags",
    ),
    # ── Temporal ─────────────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="Show me the full Meridian training timeline",
        sim_key="temporal:training_timeline",
        reasoning_type=ReasoningType.TEMPORAL,
        description="5-entry timeline: Nov 3 → Nov 28, 2025",
    ),
    # ── Aggregation ──────────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="Give me a content overview",
        sim_key="agg:content_stats",
        reasoning_type=ReasoningType.AGGREGATION,
        description="content_stats template — counts by node type",
    ),
    # ── Cross-doc entity ─────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="Tell me about PyTorch",
        sim_key="topic:pytorch",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Cross-doc topic — appears in both sample docs",
    ),
    QueryScenario(
        category="challenging",
        user_query="What did Priya Kapoor work on?",
        sim_key="person:priya_kapoor",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Person mislabelled by spaCy — test robustness",
    ),
    QueryScenario(
        category="challenging",
        user_query="Who is David Okonkwo?",
        sim_key="person:david_okonkwo",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Infrastructure lead — Hermes API owner",
    ),
    QueryScenario(
        category="challenging",
        user_query="Who is Yuki Tanaka?",
        sim_key="person:yuki_tanaka",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Evaluation lead — GGUF, LM Eval Harness",
    ),
    # ── Empty / negative ─────────────────────────────────────────────
    QueryScenario(
        category="challenging",
        user_query="Tell me about quantum computing",
        sim_key="empty",
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Entity NOT in knowledge graph — graceful empty",
    ),
    QueryScenario(
        category="challenging",
        user_query="What caused the budget overrun?",
        sim_key="empty",
        reasoning_type=ReasoningType.CAUSAL,
        description="Causal query with no graph data — graceful empty",
    ),
]


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def builder() -> ReasoningChainBuilder:
    return ReasoningChainBuilder()


@pytest.fixture(scope="module")
def prompt_builder() -> PromptBuilder:
    return PromptBuilder()


@pytest.fixture(scope="module")
def all_chains(builder) -> dict[str, tuple[QueryScenario, ReasoningChain]]:
    """Build chains for every scenario."""
    chains: dict[str, tuple[QueryScenario, ReasoningChain]] = {}
    for scenario in COMMON_QUERIES + CHALLENGING_QUERIES:
        sim_results = NEO4J_SIM[scenario.sim_key]
        chain = builder.build_chain(
            scenario.user_query,
            scenario.reasoning_type,
            sim_results,
        )
        key = f"{scenario.category}:{scenario.user_query}"
        chains[key] = (scenario, chain)
    return chains


@pytest.fixture(scope="module", autouse=True)
def write_report(all_chains, prompt_builder) -> None:
    """Write the full human-readable chain report."""
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# Reasoning Chain Test Results")
    lines.append(f"> Generated: {now}")
    lines.append("")
    lines.append("Each section shows the **exact context that would be injected")
    lines.append("into the LLM prompt** (`chain.to_llm_prompt_context()`).  The")
    lines.append("LLM's only job is to narrate this pre-computed chain.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Summary table ────────────────────────────────────────────────
    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Category | Query | Type | Steps | Confidence |")
    lines.append("|---|----------|-------|------|-------|------------|")
    for i, (key, (sc, ch)) in enumerate(all_chains.items(), 1):
        lines.append(
            f"| {i} | {sc.category} | {sc.user_query} | "
            f"`{sc.reasoning_type.value}` | {len(ch.steps)} | "
            f"{ch.total_confidence:.0%} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Per-query detail ─────────────────────────────────────────────
    for i, (key, (sc, ch)) in enumerate(all_chains.items(), 1):
        lines.append(f"## {i}. {sc.user_query}")
        lines.append("")
        lines.append(f"**Category:** {sc.category}  ")
        lines.append(f"**Description:** {sc.description}  ")
        lines.append(f"**Reasoning type:** `{sc.reasoning_type.value}`  ")
        lines.append(f"**Steps:** {len(ch.steps)}  ")
        lines.append(f"**Confidence:** {ch.total_confidence:.0%}  ")
        lines.append(f"**Conclusion:** {ch.conclusion}")
        lines.append("")
        lines.append("### Prompt Context (injected into LLM)")
        lines.append("")
        lines.append("```")
        lines.append(ch.to_llm_prompt_context())
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Write ────────────────────────────────────────────────────────
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅  Reasoning chain report written to: {OUTPUT_MD}")


# ===================================================================
# COMMON QUERY TESTS
# ===================================================================

class TestCommonPersonLookup:
    """Everyday 'who is X?' queries must produce usable chains."""

    def test_marcus_chain_has_steps(self, all_chains):
        _, chain = all_chains["common:Who is Marcus Rivera?"]
        assert len(chain.steps) >= 1

    def test_marcus_evidence_includes_name(self, all_chains):
        _, chain = all_chains["common:Who is Marcus Rivera?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Marcus Rivera" in all_evidence

    def test_marcus_evidence_includes_projects(self, all_chains):
        _, chain = all_chains["common:Who is Marcus Rivera?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Project Atlas" in all_evidence

    def test_sarah_chen_conclusion_nonempty(self, all_chains):
        _, chain = all_chains["common:Who is Sarah Chen?"]
        assert chain.conclusion
        assert len(chain.conclusion) > 10

    def test_elena_rossi_shows_affiliation(self, all_chains):
        _, chain = all_chains["common:Tell me about Professor Elena Rossi"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "University of Edinburgh" in all_evidence


class TestCommonTopicLookup:
    """Topic lookups should show related topics and subtopics."""

    def test_atlas_has_subtopics(self, all_chains):
        _, chain = all_chains["common:Tell me about Project Atlas"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Atlas v2.3" in all_evidence or "Hermes API" in all_evidence

    def test_atlas_related_topics(self, all_chains):
        _, chain = all_chains["common:Tell me about Project Atlas"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "PyTorch" in all_evidence

    def test_dpo_topic_chain(self, all_chains):
        _, chain = all_chains["common:What is DPO?"]
        assert len(chain.steps) >= 1
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "DPO" in all_evidence


class TestCommonExploration:
    """Exploration queries should group results by relationship type."""

    def test_meridian_exploration_steps(self, all_chains):
        _, chain = all_chains["common:What do I know about Meridian-7B?"]
        assert len(chain.steps) >= 2, "Should group by relationship type"

    def test_meridian_shows_people(self, all_chains):
        _, chain = all_chains["common:What do I know about Meridian-7B?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Lena Vasquez" in all_evidence


class TestCommonTemporal:
    """Temporal queries should group by topic and show dates."""

    def test_last_month_has_steps(self, all_chains):
        _, chain = all_chains["common:What happened last month?"]
        assert len(chain.steps) >= 1

    def test_last_month_mentions_topics(self, all_chains):
        _, chain = all_chains["common:What happened last month?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Meridian" in all_evidence or "DPO" in all_evidence


class TestCommonAggregation:
    """Aggregation queries should show counts."""

    def test_atlas_doc_count(self, all_chains):
        _, chain = all_chains["common:How many documents mention Project Atlas?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "1" in all_evidence or "document_count" in all_evidence
        assert "Meeting Notes" in all_evidence

    def test_top_people_multiple_results(self, all_chains):
        _, chain = all_chains["common:Who are the most mentioned people?"]
        assert len(chain.steps) >= 5  # top 10 people, each is a step

    def test_top_people_ordered(self, all_chains):
        _, chain = all_chains["common:Who are the most mentioned people?"]
        # First step should be Marcus Rivera (6 mentions, highest)
        first_evidence = " ".join(chain.steps[0].evidence)
        assert "Marcus Rivera" in first_evidence


class TestCommonRelationship:
    """Relationship queries should show connections."""

    def test_marcus_connections_has_steps(self, all_chains):
        _, chain = all_chains["common:What are the connections of Marcus Rivera?"]
        assert len(chain.steps) >= 1

    def test_marcus_connections_evidence(self, all_chains):
        _, chain = all_chains["common:What are the connections of Marcus Rivera?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Marcus Rivera" in all_evidence or "Project Atlas" in all_evidence

    def test_marcus_shows_events(self, all_chains):
        _, chain = all_chains["common:What are the connections of Marcus Rivera?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Barcelona Offsite" in all_evidence

    def test_lena_connections_shows_colleagues(self, all_chains):
        _, chain = all_chains["common:What are the connections of Lena Vasquez?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Tomás Herrera" in all_evidence or "Yuki Tanaka" in all_evidence

    def test_lena_connections_shows_projects(self, all_chains):
        _, chain = all_chains["common:What are the connections of Lena Vasquez?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Meridian-7B" in all_evidence


class TestCommonAdditionalPeople:
    """Extra common person lookups."""

    def test_tomas_herrera_expertise(self, all_chains):
        _, chain = all_chains["common:Who is Tomás Herrera?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "DPO" in all_evidence
        assert "toxicity" in all_evidence.lower()

    def test_constitutional_ai_parent(self, all_chains):
        _, chain = all_chains["common:Tell me about Constitutional AI"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "AI Safety" in all_evidence


# ===================================================================
# CHALLENGING QUERY TESTS
# ===================================================================

class TestMultiHopChains:
    """Multi-hop paths must show intermediate nodes and hop count."""

    def test_marcus_to_mit_3_hops(self, all_chains):
        _, chain = all_chains["challenging:How does Marcus Rivera connect to MIT CSAIL?"]
        assert len(chain.steps) >= 1
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Marcus Rivera" in all_evidence
        assert "MIT CSAIL" in all_evidence

    def test_marcus_to_mit_path_through_moe_and_thornton(self, all_chains):
        _, chain = all_chains["challenging:How does Marcus Rivera connect to MIT CSAIL?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "mixture-of-experts" in all_evidence
        assert "James Thornton" in all_evidence

    def test_marcus_to_mit_conclusion_correct_intermediates(self, all_chains):
        _, chain = all_chains["challenging:How does Marcus Rivera connect to MIT CSAIL?"]
        # 3-hop path: Marcus→MoE→Thornton→MIT = 2 intermediates
        assert "2 intermediate" in chain.conclusion or "connects to" in chain.conclusion

    def test_fatima_to_constitutional_ai_4_hops(self, all_chains):
        _, chain = all_chains["challenging:How does Fatima Al-Rashidi connect to Constitutional AI?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Fatima Al-Rashidi" in all_evidence
        assert "Constitutional AI" in all_evidence
        assert "Nexus-Instruct-v3" in all_evidence
        assert "DPO" in all_evidence

    def test_scale_ai_to_meridian_chat_3_hops(self, all_chains):
        _, chain = all_chains["challenging:What is the relationship between Scale AI and Meridian-7B-Chat?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Scale AI" in all_evidence
        assert "Lisa Nguyen" in all_evidence
        assert "Meridian-7B-Chat" in all_evidence

    def test_rossi_to_patent_2_hops(self, all_chains):
        _, chain = all_chains["challenging:How are Professor Rossi and patent PA-2025-0892 connected?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Rossi" in all_evidence
        assert "two-pass toxicity filtering" in all_evidence
        assert "Patent PA-2025-0892" in all_evidence

    def test_eu_ai_act_to_atlas_via_safety(self, all_chains):
        _, chain = all_chains["challenging:What is the relationship between EU AI Act and Project Atlas?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "EU AI Act" in all_evidence
        assert "AI Safety" in all_evidence
        assert "Project Atlas" in all_evidence

    def test_multi_hop_conclusion_mentions_connection(self, all_chains):
        _, chain = all_chains["challenging:How does Marcus Rivera connect to MIT CSAIL?"]
        assert "connect" in chain.conclusion.lower() or "found" in chain.conclusion.lower()


class TestCausalChains:
    """Causal chains must preserve temporal ordering and show evidence."""

    def test_gpu_failure_has_5_steps(self, all_chains):
        _, chain = all_chains["challenging:What caused the GPU failure incident?"]
        assert len(chain.steps) >= 4, f"Only {len(chain.steps)} steps for 5-event causal chain"

    def test_gpu_failure_evidence_ordered(self, all_chains):
        _, chain = all_chains["challenging:What caused the GPU failure incident?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "temperature" in all_evidence.lower() or "87" in all_evidence
        assert "ECC" in all_evidence or "memory error" in all_evidence.lower()

    def test_truthfulqa_causal_chain(self, all_chains):
        _, chain = all_chains["challenging:What caused the TruthfulQA score to improve?"]
        assert len(chain.steps) >= 4
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "34.2" in all_evidence or "TruthfulQA" in all_evidence
        assert "Rossi" in all_evidence or "two-pass" in all_evidence.lower()

    def test_causal_conclusion_mentions_events(self, all_chains):
        _, chain = all_chains["challenging:What caused the GPU failure incident?"]
        assert "5" in chain.conclusion or "causal" in chain.conclusion.lower()

    def test_list_bias_causal_3_steps(self, all_chains):
        _, chain = all_chains["challenging:What caused the list bias in Meridian?"]
        assert len(chain.steps) >= 3
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Nexus-Instruct-v3" in all_evidence
        assert "34%" in all_evidence or "bullet" in all_evidence.lower()
        assert "Fatima" in all_evidence or "rebalanc" in all_evidence.lower()


class TestComparisonChains:
    """Comparison chains must show both entities side-by-side."""

    def test_pytorch_vs_tensorflow(self, all_chains):
        _, chain = all_chains["challenging:Compare PyTorch and TensorFlow"]
        assert len(chain.steps) >= 2, "Need at least 2 steps (one per entity)"
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "PyTorch" in all_evidence
        assert "TensorFlow" in all_evidence

    def test_dpo_vs_sft(self, all_chains):
        _, chain = all_chains["challenging:Compare DPO and SFT training approaches"]
        assert len(chain.steps) >= 2
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "DPO" in all_evidence
        assert "SFT" in all_evidence

    def test_comparison_conclusion_has_winner(self, all_chains):
        _, chain = all_chains["challenging:Compare PyTorch and TensorFlow"]
        assert "leads" in chain.conclusion.lower() or "comparison" in chain.conclusion.lower()


class TestChallengingExploration:
    """Exploration of Project Atlas neighborhood."""

    def test_atlas_exploration_groups_by_rel(self, all_chains):
        _, chain = all_chains["challenging:What is connected to Project Atlas?"]
        assert len(chain.steps) >= 3, "Should group ABOUT, RELATED_TO, SUBTOPIC_OF, WORKED_ON, FLAGGED_IN"

    def test_atlas_exploration_shows_people(self, all_chains):
        _, chain = all_chains["challenging:What is connected to Project Atlas?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Marcus Rivera" in all_evidence
        assert "David Okonkwo" in all_evidence

    def test_atlas_exploration_shows_eu_flag(self, all_chains):
        _, chain = all_chains["challenging:What is connected to Project Atlas?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "EU AI Act" in all_evidence


class TestChallengingTimeline:
    """Full training timeline."""

    def test_training_timeline_5_entries(self, all_chains):
        _, chain = all_chains["challenging:Show me the full Meridian training timeline"]
        # 5 documents with multiple topic groups
        assert len(chain.steps) >= 4

    def test_training_timeline_mentions_meridian(self, all_chains):
        _, chain = all_chains["challenging:Show me the full Meridian training timeline"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Meridian" in all_evidence

    def test_training_timeline_shows_dates(self, all_chains):
        _, chain = all_chains["challenging:Show me the full Meridian training timeline"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "2025-11-03" in all_evidence
        assert "2025-11-28" in all_evidence


class TestChallengingContentStats:
    """Content overview aggregation."""

    def test_content_stats_steps(self, all_chains):
        _, chain = all_chains["challenging:Give me a content overview"]
        assert len(chain.steps) >= 4

    def test_content_stats_shows_counts(self, all_chains):
        _, chain = all_chains["challenging:Give me a content overview"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Topics" in all_evidence or "People" in all_evidence


class TestChallengingAdditionalPeople:
    """Extra person lookups for people with distinct graph shapes."""

    def test_david_okonkwo_hermes(self, all_chains):
        _, chain = all_chains["challenging:Who is David Okonkwo?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "Hermes API" in all_evidence
        assert "Infrastructure" in all_evidence

    def test_yuki_tanaka_evaluation(self, all_chains):
        _, chain = all_chains["challenging:Who is Yuki Tanaka?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "GGUF" in all_evidence or "HellaSwag" in all_evidence
        assert "Evaluation" in all_evidence

    def test_priya_kapoor_compliance(self, all_chains):
        _, chain = all_chains["challenging:What did Priya Kapoor work on?"]
        all_evidence = " ".join(
            ev for step in chain.steps for ev in step.evidence
        )
        assert "EU AI Act" in all_evidence
        assert "ONNX" in all_evidence


class TestEmptyResults:
    """Queries with no graph data must produce graceful chains."""

    def test_missing_entity_chain(self, all_chains):
        _, chain = all_chains["challenging:Tell me about quantum computing"]
        assert chain.conclusion
        assert "not found" in chain.conclusion.lower() or len(chain.steps) >= 1

    def test_missing_causal_chain(self, all_chains):
        _, chain = all_chains["challenging:What caused the budget overrun?"]
        assert chain.conclusion
        # Should not crash, should produce a valid chain
        assert chain.total_confidence >= 0.0


class TestChainStructuralInvariants:
    """Every chain must satisfy structural contracts."""

    @pytest.mark.parametrize(
        "key",
        [k for k in (
            [f"common:{s.user_query}" for s in COMMON_QUERIES]
            + [f"challenging:{s.user_query}" for s in CHALLENGING_QUERIES]
        )],
    )
    def test_chain_has_query(self, all_chains, key):
        _, chain = all_chains[key]
        assert chain.query, "Chain must store the original query"

    @pytest.mark.parametrize(
        "key",
        [k for k in (
            [f"common:{s.user_query}" for s in COMMON_QUERIES]
            + [f"challenging:{s.user_query}" for s in CHALLENGING_QUERIES]
        )],
    )
    def test_chain_has_reasoning_type(self, all_chains, key):
        _, chain = all_chains[key]
        assert chain.reasoning_type, "Chain must have a reasoning type"

    @pytest.mark.parametrize(
        "key",
        [k for k in (
            [f"common:{s.user_query}" for s in COMMON_QUERIES]
            + [f"challenging:{s.user_query}" for s in CHALLENGING_QUERIES]
        )],
    )
    def test_chain_has_conclusion(self, all_chains, key):
        _, chain = all_chains[key]
        assert chain.conclusion, "Chain must have a conclusion"

    @pytest.mark.parametrize(
        "key",
        [k for k in (
            [f"common:{s.user_query}" for s in COMMON_QUERIES]
            + [f"challenging:{s.user_query}" for s in CHALLENGING_QUERIES]
        )],
    )
    def test_confidence_in_range(self, all_chains, key):
        _, chain = all_chains[key]
        assert 0.0 <= chain.total_confidence <= 1.0

    @pytest.mark.parametrize(
        "key",
        [k for k in (
            [f"common:{s.user_query}" for s in COMMON_QUERIES]
            + [f"challenging:{s.user_query}" for s in CHALLENGING_QUERIES]
        )],
    )
    def test_step_numbers_sequential(self, all_chains, key):
        _, chain = all_chains[key]
        for i, step in enumerate(chain.steps):
            assert step.step_number == i + 1, (
                f"Step {i} has number {step.step_number}, expected {i + 1}"
            )

    @pytest.mark.parametrize(
        "key",
        [k for k in (
            [f"common:{s.user_query}" for s in COMMON_QUERIES]
            + [f"challenging:{s.user_query}" for s in CHALLENGING_QUERIES]
        )],
    )
    def test_prompt_context_is_string(self, all_chains, key):
        _, chain = all_chains[key]
        ctx = chain.to_llm_prompt_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 20


class TestPromptContextFormat:
    """The prompt context must contain required structural markers."""

    @pytest.mark.parametrize(
        "key",
        [f"common:{s.user_query}" for s in COMMON_QUERIES[:3]],
    )
    def test_has_query_line(self, all_chains, key):
        _, chain = all_chains[key]
        ctx = chain.to_llm_prompt_context()
        assert "QUERY:" in ctx

    @pytest.mark.parametrize(
        "key",
        [f"common:{s.user_query}" for s in COMMON_QUERIES[:3]],
    )
    def test_has_reasoning_type_line(self, all_chains, key):
        _, chain = all_chains[key]
        ctx = chain.to_llm_prompt_context()
        assert "REASONING TYPE:" in ctx

    @pytest.mark.parametrize(
        "key",
        [f"common:{s.user_query}" for s in COMMON_QUERIES[:3]],
    )
    def test_has_confidence_line(self, all_chains, key):
        _, chain = all_chains[key]
        ctx = chain.to_llm_prompt_context()
        assert "CONFIDENCE:" in ctx

    @pytest.mark.parametrize(
        "key",
        [f"common:{s.user_query}" for s in COMMON_QUERIES[:3]],
    )
    def test_has_conclusion_line(self, all_chains, key):
        _, chain = all_chains[key]
        ctx = chain.to_llm_prompt_context()
        assert "CONCLUSION:" in ctx

    @pytest.mark.parametrize(
        "key",
        [f"common:{s.user_query}" for s in COMMON_QUERIES[:3]],
    )
    def test_has_reasoning_chain_section(self, all_chains, key):
        _, chain = all_chains[key]
        ctx = chain.to_llm_prompt_context()
        assert "REASONING CHAIN:" in ctx
