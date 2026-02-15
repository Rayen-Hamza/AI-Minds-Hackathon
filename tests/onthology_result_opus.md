# Ontology Extraction Report
> Generated: 2026-02-15 02:29:22

---

## Summary

| Metric | Value |
|--------|-------|
| Total unique entities | 217 |
| Total relationships (SPO triples) | 54 |
| Distinct Neo4j labels | 7 |
| Documents processed | 2 |

## Entity Breakdown by Label

| Neo4j Label | Count |
|-------------|-------|
| Topic | 79 |
| Organization | 49 |
| Event | 36 |
| Person | 28 |
| Location | 17 |
| Concept | 6 |
| Project | 2 |

### Concept (6)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| English | `LANGUAGE` | 0.80 | 1 | sample2_research_log |
| European | `NORP` | 0.78 | 1 | sample1_meeting_notes |
| Evaluation | `NORP` | 0.78 | 1 | sample2_research_log |
| Flash Attention 2 | `WORK_OF_ART` | 0.55 | 1 | sample2_research_log |
| Hugging Face Hub
- February 15 | `WORK_OF_ART` | 0.55 | 1 | sample2_research_log |
| the Nexus-Instruct-v3 | `LAW` | 0.60 | 1 | sample2_research_log |

### Event (36)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| 11.2 days | `DATE` | 0.85 | 1 | sample2_research_log |
| 14 days | `DATE` | 0.85 | 1 | sample2_research_log |
| 2-day | `DATE` | 0.85 | 1 | sample2_research_log |
| 2025-11-03 | `DATE` | 0.85 | 1 | sample2_research_log |
| 2025-12-19 | `DATE` | 0.85 | 1 | sample2_research_log |
| 2026 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| 2026-01-14 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| 4096 | `DATE` | 0.85 | 1 | sample2_research_log |
| 48 hours | `TIME` | 0.75 | 1 | sample2_research_log |
| April 5 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| December 12, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| December 15 | `DATE` | 0.85 | 1 | sample2_research_log |
| December 19, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| December 5, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| February 1 | `DATE` | 0.85 | 1 | sample2_research_log |
| February 10-12 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| February 28, 2026 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| February 5 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| HW-2025-1847 | `DATE` | 0.85 | 1 | sample2_research_log |
| January 13 | `DATE` | 0.85 | 1 | sample2_research_log |
| January 17 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| January 21 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| January 25 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| January 28 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| January 6, 2026 | `DATE` | 0.85 | 1 | sample2_research_log |
| March 1, 2026 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| March 15-18 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| May 20-22 | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| Mistral-7B-v0.1 | `DATE` | 0.85 | 1 | sample2_research_log |
| November 12, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| November 19, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| November 28, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| November 3, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| November 7, 2025 | `DATE` | 0.85 | 1 | sample2_research_log |
| last week | `DATE` | 0.85 | 1 | sample1_meeting_notes |
| more than 30 minutes | `TIME` | 0.75 | 1 | sample2_research_log |

### Location (17)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| Amsterdam | `GPE` | 0.88 | 2 | sample1_meeting_notes, sample2_research_log |
| Toronto | `GPE` | 0.88 | 2 | sample1_meeting_notes, sample2_research_log |
| AI | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Barcelona | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Berlin | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Condor | `GPE` | 0.88 | 1 | sample2_research_log |
| Dublin | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Grafana | `GPE` | 0.88 | 1 | sample2_research_log |
| Las Vegas | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| LinkedIn | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| London | `GPE` | 0.88 | 1 | sample2_research_log |
| Paris | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Priya Kapoor | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Rivera | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Spain | `GPE` | 0.88 | 1 | sample1_meeting_notes |
| Stockholm | `GPE` | 0.88 | 1 | sample2_research_log |
| Vienna | `GPE` | 0.88 | 1 | sample1_meeting_notes |

### Organization (49)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| GPU | `ORG` | 0.80 | 2 | sample1_meeting_notes, sample2_research_log |
| Nexus Technologies | `ORG` | 0.80 | 2 | sample1_meeting_notes, sample2_research_log |
| AI Safety | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| AMPS | `ORG` | 0.80 | 1 | sample2_research_log |
| AWS S3 | `ORG` | 0.80 | 1 | sample2_research_log |
| Amara Osei's | `ORG` | 0.80 | 1 | sample2_research_log |
| Amazon Web Services | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Atlas Update | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| CFO | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Complete PyTorch | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Computer Science and Artificial
Intelligence Laboratory | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Constitutional AI | `ORG` | 0.80 | 1 | sample2_research_log |
| CoreWeave | `ORG` | 0.80 | 1 | sample2_research_log |
| DPO | `ORG` | 0.80 | 1 | sample2_research_log |
| Dataset | `ORG` | 0.80 | 1 | sample2_research_log |
| DeepSpeed | `ORG` | 0.80 | 1 | sample2_research_log |
| Direct Preference Optimization | `ORG` | 0.80 | 1 | sample2_research_log |
| Distributed Training Incident & Recovery
 | `ORG` | 0.80 | 1 | sample2_research_log |
| Finalize Hermes API | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| GGUF | `ORG` | 0.80 | 1 | sample2_research_log |
| GitHub | `ORG` | 0.80 | 1 | sample2_research_log |
| HellaSwag | `ORG` | 0.80 | 1 | sample2_research_log |
| Hugging Face | `ORG` | 0.80 | 1 | sample2_research_log |
| Kubernetes | `ORG` | 0.80 | 1 | sample2_research_log |
| MIT | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| ML Engineering | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| MLOps | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Marcus Rivera | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Microsoft | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Nexus Red Team | `ORG` | 0.80 | 1 | sample2_research_log |
| Nexus-Instruct-v3 | `ORG` | 0.80 | 1 | sample2_research_log |
| Pile | `ORG` | 0.80 | 1 | sample2_research_log |
| Post Foundation Models | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| Project Athena | `ORG` | 0.80 | 1 | sample2_research_log |
| Project Atlas | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| PyTorch | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| RedPajama | `ORG` | 0.80 | 1 | sample2_research_log |
| SFT | `ORG` | 0.80 | 1 | sample2_research_log |
| SQuAD-Finance | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| SRE | `ORG` | 0.80 | 1 | sample2_research_log |
| Scale AI | `ORG` | 0.80 | 1 | sample2_research_log |
| Stack | `ORG` | 0.80 | 1 | sample2_research_log |
| TRL | `ORG` | 0.80 | 1 | sample2_research_log |
| TensorFlow | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| University of
Edinburgh | `ORG` | 0.80 | 1 | sample2_research_log |
| Upcoming Events

- | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| the Data Quality | `ORG` | 0.80 | 1 | sample2_research_log |
| the Partnership on AI | `ORG` | 0.80 | 1 | sample1_meeting_notes |
| the World AI Summit | `ORG` | 0.80 | 1 | sample1_meeting_notes |

### Person (28)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| Amara Osei | `PERSON` | 0.92 | 1 | sample2_research_log |
| Atlas | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Carlos Mendez | `PERSON` | 0.92 | 1 | sample2_research_log |
| Checkpoint | `PERSON` | 0.92 | 1 | sample2_research_log |
| Claude 4 | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| David Okonkwo | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| David Okonkwo's | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Elena Rossi | `PERSON` | 0.92 | 1 | sample2_research_log |
| Emily Zhang | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Fatima
Al-Rashidi | `PERSON` | 0.92 | 1 | sample2_research_log |
| Fatima Al-Rashidi's | `PERSON` | 0.92 | 1 | sample2_research_log |
| James Thornton's | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Jin Park | `PERSON` | 0.92 | 1 | sample2_research_log |
| Lambda Cloud | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Lena Vasquez | `PERSON` | 0.92 | 1 | sample2_research_log |
| Lena Vasquez
Dates | `PERSON` | 0.92 | 1 | sample2_research_log |
| Lisa Nguyen | `PERSON` | 0.92 | 1 | sample2_research_log |
| Q8_0 | `PERSON` | 0.92 | 1 | sample2_research_log |
| Robert Kim | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Rossi | `PERSON` | 0.92 | 1 | sample2_research_log |
| Sarah Chen | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Thornton | `PERSON` | 0.92 | 1 | sample1_meeting_notes |
| Tomás Herrera | `PERSON` | 0.92 | 1 | sample2_research_log |
| Tomás Herrera
 | `PERSON` | 0.92 | 1 | sample2_research_log |
| Tomás Herrera re-ran | `PERSON` | 0.92 | 1 | sample2_research_log |
| Tomás Herrera's | `PERSON` | 0.92 | 1 | sample2_research_log |
| Yuki Tanaka | `PERSON` | 0.92 | 1 | sample2_research_log |
| Yuki Tanaka's | `PERSON` | 0.92 | 1 | sample2_research_log |

### Project (2)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| MoE | `PRODUCT` | 0.55 | 1 | sample1_meeting_notes |
| Workshop | `PRODUCT` | 0.55 | 1 | sample1_meeting_notes |

### Topic (79)

| Entity | spaCy Label | Confidence | Mentions | Sources |
|--------|-------------|------------|----------|---------|
| 1 | `CARDINAL` | 0.50 | 2 | sample1_meeting_notes, sample2_research_log |
| 2 | `CARDINAL` | 0.50 | 2 | sample1_meeting_notes, sample2_research_log |
| 3 | `CARDINAL` | 0.50 | 2 | sample1_meeting_notes, sample2_research_log |
| 4 | `CARDINAL` | 0.50 | 2 | sample1_meeting_notes, sample2_research_log |
| 5 | `MONEY` | 0.50 | 2 | sample1_meeting_notes, sample2_research_log |
| ## 2 | `MONEY` | 0.50 | 1 | sample1_meeting_notes |
| $2.4M | `MONEY` | 0.50 | 1 | sample1_meeting_notes |
| 0.1 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 0.3 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 0.3% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 0.5 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 1,000 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 1,800 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 10% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 11.7 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 12,400 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 120ms | `ORDINAL` | 0.50 | 1 | sample1_meeting_notes |
| 127 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 128 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 14 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 14.3% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 15% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 15,000 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 150,000 | `MONEY` | 0.50 | 1 | sample1_meeting_notes |
| 18.1% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 18.2 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 1e-5 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 2,000 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 2,300 | `MONEY` | 0.50 | 1 | sample2_research_log |
| 2.0 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 22,000 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 22,847 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 23% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 28.7% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 312,000 | `MONEY` | 0.50 | 1 | sample2_research_log |
| 32 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 34% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 34.1% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 34.2% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 38.1% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 380,000 | `MONEY` | 0.50 | 1 | sample2_research_log |
| 39.8% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 40% | `PERCENT` | 0.50 | 1 | sample1_meeting_notes |
| 42.1% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 44.8% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 4521 | `MONEY` | 0.50 | 1 | sample2_research_log |
| 47.3% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 48,200 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 5% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 50,000 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 51.2% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 52.7% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 520,000 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 524,288 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 6 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 6.8 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 6.9 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 62.3% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 68,000 | `MONEY` | 0.50 | 1 | sample2_research_log |
| 7.2 / 10 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 7.8 / 10 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 70% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 71.2% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 73.9% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 76.4% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 8 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 8.4 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 847 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 87 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 87,500 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| 94.2% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| 96.4% | `PERCENT` | 0.50 | 1 | sample2_research_log |
| Meridian-7B | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| at least 3 | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| first | `ORDINAL` | 0.50 | 1 | sample2_research_log |
| node | `CARDINAL` | 0.50 | 1 | sample2_research_log |
| second | `ORDINAL` | 0.50 | 1 | sample2_research_log |
| three | `CARDINAL` | 0.50 | 1 | sample1_meeting_notes |
| two | `CARDINAL` | 0.50 | 1 | sample2_research_log |

## Extracted Relationships (SPO Triples)

| # | Subject | Predicate | Object | Source |
|---|---------|-----------|--------|--------|
| 1 | Project Atlas Update

Marcus Rivera | `present` | the latest progress on Project Atlas | sample1_meeting_notes |
| 2 | The team | `migrate` | the core inference engine from TensorFlow | sample1_meeting_notes |
| 3 | the new ONNX export pipeline | `work` | staging at the Berlin datacenter | sample1_meeting_notes |
| 4 | - Atlas v2.3 release | `schedule` | February 28, 2026 | sample1_meeting_notes |
| 5 | David Okonkwo | `lead` | the integration with the Hermes API gateway | sample1_meeting_notes |
| 6 | Research Collaboration with MIT CSAIL

Emily Zhang | `report` | the partnership with MIT's Computer Science and Artificial
Intelligence Laboratory (CSAIL) | sample1_meeting_notes |
| 7 | Professor James Thornton's group | `share` | print | sample1_meeting_notes |
| 8 | that | `reduce` | our model
size | sample1_meeting_notes |
| 9 | Competitive Analysis

Priya Kapoor | `share` | intelligence on competitor activity | sample1_meeting_notes |
| 10 | - Anthropic | `release` | Claude 4 | sample1_meeting_notes |
| 11 | Microsoft | `demonstrate` | what | sample1_meeting_notes |
| 12 | Google DeepMind | `publish` | a paper | sample1_meeting_notes |
| 13 | that | `contradict` | some of our safety assumptions | sample1_meeting_notes |
| 14 | David Okonkwo | `raise` | concerns about our position in the European market | sample1_meeting_notes |
| 15 | The EU AI
Act enforcement | `begin` | ## 4 | sample1_meeting_notes |
| 16 | our compliance team in Dublin | `flag` | three risk areas in the Atlas pipeline | sample1_meeting_notes |
| 17 | Robert Kim | `approve` | a total hiring budget of $2.4M for Q1-Q2 across all AI teams | sample1_meeting_notes |
| 18 | Atlas | `v2.3` | showcase to the board of directors | sample1_meeting_notes |
| 19 | Sarah Chen | `keynote` | the World AI Summit in Amsterdam | sample1_meeting_notes |
| 20 | = | `start` | the full pre-training run for Meridian-7B on the Condor cluster (128x
NVIDIA H100 GPUs) at the Stockholm datacenter | sample2_research_log |
| 21 | Loss curve | `look` | step 12,400 | sample2_research_log |
| 22 | Validation perplexity on the Pile | `drop` | 18.2 | sample2_research_log |
| 23 | our MMLU scores | `lag` | expectations | sample2_research_log |
| 24 | the math subset | `pull` | mathematical content | sample2_research_log |
| 25 | Carlos Mendez | `approve` | the data mixture change | sample2_research_log |
| 26 | math validation
loss | `drop` | 2,000 steps | sample2_research_log |
| 27 | GPU node worker-gpu-089 | `throw` | an ECC
(Error-Correcting Code) memory error | sample2_research_log |
| 28 | DeepSpeed's elastic training module | `detect` | the failure | sample2_research_log |
| 29 | the automatic recovery | `corrupt` | the optimizer state | sample2_research_log |
| 30 | Root | `cause` | The CoreWeave team (contact: | sample2_research_log |
| 31 | - worker-gpu-089 | `flag` | elevated temperature readings (87°C sustained) | sample2_research_log |
| 32 | the node | `have` | a failing
  cooling fan assembly | sample2_research_log |
| 33 | - Recommendation: | `implement` | pre-emptive node draining | sample2_research_log |
| 34 | === Entry 4 — November 19, 2025 === | `cross` | the 50,000-step milestone | sample2_research_log |
| 35 | )
- HumanEval (code): 28.7%

Yuki Tanaka's team | `run` | the full LM Evaluation Harness | sample2_research_log |
| 36 | we | `score` | 34.2% | sample2_research_log |
| 37 | She | `recommend` | a
two-pass filtering approach: first pass for genuine toxicity, second pass
for factual calibration | sample2_research_log |
| 38 | Model artifacts | `upload` | Hugging Face Hub: | sample2_research_log |
| 39 | models.nexus.internal/meridian/7b-v1-base

Post-training plan | `agree` | Carlos Mendez:
1 | sample2_research_log |
| 40 | the SFT training on 32 GPUs | `hit` | an OOM (Out of Memory) error at batch
size 8 with sequence length 4096 | sample2_research_log |
| 41 | Amara Osei's infrastructure team | `deploy` | a new monitoring dashboard | sample2_research_log |
| 42 | === | `SFT` | training | sample2_research_log |
| 43 | Scale AI | `deliver` | 48,200 preference pairs (96.4% of contracted volume) | sample2_research_log |
| 44 | Lisa Nguyen explained the shortfall — 1,800 pairs flagged by their internal
QA for low inter-annotator agreement and removed | `explain` | the shortfall | sample2_research_log |
| 45 | Tomás Herrera | `start` | DPO training | sample2_research_log |
| 46 | Meridian-7B-SFT | `have` | a bias toward
generating lists | sample2_research_log |
| 47 | Root cause | `trace` | the Nexus-Instruct-v3 dataset | sample2_research_log |
| 48 | 34% of responses | `use` | bullet-point
format | sample2_research_log |
| 49 | Fatima Al-Rashidi's team in Toronto | `rebalance` | the dataset | sample2_research_log |
| 50 | Professor Elena Rossi | `visit` | our London office | sample2_research_log |
| 51 | the "red-teaming then
revise" loop | `do` | at least 3 diverse evaluator personas | sample2_research_log |
| 52 | Carlos Mendez | `approve` | the model for internal beta release | sample2_research_log |
| 53 | The model | `generate` | plausible-sounding but fabricated citations | sample2_research_log |
| 54 | Meridian-7B | `train` | English | sample2_research_log |

## Cross-Document Entities

Entities that appear in **both** sample documents:

| Entity | Label | Sources |
|--------|-------|---------|
| 1 | Topic | sample1_meeting_notes, sample2_research_log |
| 2 | Topic | sample1_meeting_notes, sample2_research_log |
| 3 | Topic | sample1_meeting_notes, sample2_research_log |
| 4 | Topic | sample1_meeting_notes, sample2_research_log |
| 5 | Topic | sample1_meeting_notes, sample2_research_log |
| Amsterdam | Location | sample1_meeting_notes, sample2_research_log |
| GPU | Organization | sample1_meeting_notes, sample2_research_log |
| Nexus Technologies | Organization | sample1_meeting_notes, sample2_research_log |
| Toronto | Location | sample1_meeting_notes, sample2_research_log |

## High-Confidence Entities (≥ 0.85)

| Entity | Label | Confidence |
|--------|-------|------------|
| Amara Osei | Person | 0.92 |
| Atlas | Person | 0.92 |
| Carlos Mendez | Person | 0.92 |
| Checkpoint | Person | 0.92 |
| Claude 4 | Person | 0.92 |
| David Okonkwo | Person | 0.92 |
| David Okonkwo's | Person | 0.92 |
| Elena Rossi | Person | 0.92 |
| Emily Zhang | Person | 0.92 |
| Fatima
Al-Rashidi | Person | 0.92 |
| Fatima Al-Rashidi's | Person | 0.92 |
| James Thornton's | Person | 0.92 |
| Jin Park | Person | 0.92 |
| Lambda Cloud | Person | 0.92 |
| Lena Vasquez | Person | 0.92 |
| Lena Vasquez
Dates | Person | 0.92 |
| Lisa Nguyen | Person | 0.92 |
| Q8_0 | Person | 0.92 |
| Robert Kim | Person | 0.92 |
| Rossi | Person | 0.92 |
| Sarah Chen | Person | 0.92 |
| Thornton | Person | 0.92 |
| Tomás Herrera | Person | 0.92 |
| Tomás Herrera
 | Person | 0.92 |
| Tomás Herrera re-ran | Person | 0.92 |
| Tomás Herrera's | Person | 0.92 |
| Yuki Tanaka | Person | 0.92 |
| Yuki Tanaka's | Person | 0.92 |
| AI | Location | 0.88 |
| Amsterdam | Location | 0.88 |
| Barcelona | Location | 0.88 |
| Berlin | Location | 0.88 |
| Condor | Location | 0.88 |
| Dublin | Location | 0.88 |
| Grafana | Location | 0.88 |
| Las Vegas | Location | 0.88 |
| LinkedIn | Location | 0.88 |
| London | Location | 0.88 |
| Paris | Location | 0.88 |
| Priya Kapoor | Location | 0.88 |
| Rivera | Location | 0.88 |
| Spain | Location | 0.88 |
| Stockholm | Location | 0.88 |
| Toronto | Location | 0.88 |
| Vienna | Location | 0.88 |
| 11.2 days | Event | 0.85 |
| 14 days | Event | 0.85 |
| 2-day | Event | 0.85 |
| 2025-11-03 | Event | 0.85 |
| 2025-12-19 | Event | 0.85 |
| 2026 | Event | 0.85 |
| 2026-01-14 | Event | 0.85 |
| 4096 | Event | 0.85 |
| April 5 | Event | 0.85 |
| December 12, 2025 | Event | 0.85 |
| December 15 | Event | 0.85 |
| December 19, 2025 | Event | 0.85 |
| December 5, 2025 | Event | 0.85 |
| February 1 | Event | 0.85 |
| February 10-12 | Event | 0.85 |
| February 28, 2026 | Event | 0.85 |
| February 5 | Event | 0.85 |
| HW-2025-1847 | Event | 0.85 |
| January 13 | Event | 0.85 |
| January 17 | Event | 0.85 |
| January 21 | Event | 0.85 |
| January 25 | Event | 0.85 |
| January 28 | Event | 0.85 |
| January 6, 2026 | Event | 0.85 |
| March 1, 2026 | Event | 0.85 |
| March 15-18 | Event | 0.85 |
| May 20-22 | Event | 0.85 |
| Mistral-7B-v0.1 | Event | 0.85 |
| November 12, 2025 | Event | 0.85 |
| November 19, 2025 | Event | 0.85 |
| November 28, 2025 | Event | 0.85 |
| November 3, 2025 | Event | 0.85 |
| November 7, 2025 | Event | 0.85 |
| last week | Event | 0.85 |

## Detected Topics per Document

### sample1_meeting_notes

- Marcus Rivera
- Atlas Update
- Project Atlas
- TensorFlow
- PyTorch
- Amazon Web Services
- MIT
- Computer Science and Artificial
Intelligence Laboratory
- SQuAD-Finance
- GPU
- CFO
- Microsoft
- ML Engineering
- MLOps
- AI Safety
- the Partnership on AI
- Upcoming Events

-
- the World AI Summit
- Complete PyTorch
- Finalize Hermes API
- Post Foundation Models
- Nexus Technologies
- 120ms
- ## 2
- 40%
- MoE
- 150,000
- European
- three
- 4
- $2.4M
- 5
- Workshop
- 1
- 2
- 3

### sample2_research_log

- Distributed Training Incident & Recovery

- Dataset
- RedPajama
- CoreWeave
- AWS S3
- Pile
- HellaSwag
- AMPS
- Stack
- GPU
- DeepSpeed
- SRE
- node
- University of
Edinburgh
- Condor
- GitHub
- SFT
- Nexus-Instruct-v3
- Direct Preference Optimization
- DPO
- Constitutional AI
- the Data Quality
- Scale AI
- Amara Osei's
- TRL
- Hugging Face
- Nexus Red Team
- Kubernetes
- Amara Osei
- Nexus Technologies
- GGUF
- Project Athena
- 1
- Meridian-7B
- 3
- 1e-5
- 128
- 524,288
- 380,000
- 1,000
- 2
- 12,400
- 18.2
- 11.7
- 62.3%
- Evaluation
- 70%
- 15%
- 10%
- 5%
- 15,000
- 0.3%
- 23%
- 2,000
- 22,847
- node
- 127
- 87
- 22,000
- 847
- 2,300
- 4
- 50,000
- 8.4
- 71.2%
- 5
- 44.8%
- 38.1%
- 28.7%
- 34.2%
- 42.1%
- two
- first
- second
- 4521
- 87,500
- 6.8
- 76.4%
- 51.2%
- 34.1%
- 39.8%
- 73.9%
- 52.7%
- 14
- 312,000
- 68,000
- 6
- 520,000
- 32
- 8
- Flash Attention 2
- 7.2 / 10
- 6.9
- 2.0
- 14.3%
- 48,200
- 96.4%
- 1,800
- 0.1
- 0.3
- 0.5
- the Nexus-Instruct-v3
- 34%
- at least 3
- 7.8 / 10
- 18.1%
- 47.3%
- 94.2%
- Hugging Face Hub
- February 15
- English

## Relationship Network (Adjacency View)

**)
- HumanEval (code): 28.7%

Yuki Tanaka's team**
  → `run` → the full LM Evaluation Harness

**- Anthropic**
  → `release` → Claude 4

**- Atlas v2.3 release**
  → `schedule` → February 28, 2026

**- Recommendation:**
  → `implement` → pre-emptive node draining

**- worker-gpu-089**
  → `flag` → elevated temperature readings (87°C sustained)

**34% of responses**
  → `use` → bullet-point
format

**=**
  → `start` → the full pre-training run for Meridian-7B on the Condor cluster (128x
NVIDIA H100 GPUs) at the Stockholm datacenter

**===**
  → `SFT` → training

**=== Entry 4 — November 19, 2025 ===**
  → `cross` → the 50,000-step milestone

**Amara Osei's infrastructure team**
  → `deploy` → a new monitoring dashboard

**Atlas**
  → `v2.3` → showcase to the board of directors

**Carlos Mendez**
  → `approve` → the data mixture change
  → `approve` → the model for internal beta release

**Competitive Analysis

Priya Kapoor**
  → `share` → intelligence on competitor activity

**David Okonkwo**
  → `lead` → the integration with the Hermes API gateway
  → `raise` → concerns about our position in the European market

**DeepSpeed's elastic training module**
  → `detect` → the failure

**Fatima Al-Rashidi's team in Toronto**
  → `rebalance` → the dataset

**GPU node worker-gpu-089**
  → `throw` → an ECC
(Error-Correcting Code) memory error

**Google DeepMind**
  → `publish` → a paper

**Lisa Nguyen explained the shortfall — 1,800 pairs flagged by their internal
QA for low inter-annotator agreement and removed**
  → `explain` → the shortfall

**Loss curve**
  → `look` → step 12,400

**Meridian-7B**
  → `train` → English

**Meridian-7B-SFT**
  → `have` → a bias toward
generating lists

**Microsoft**
  → `demonstrate` → what

**Model artifacts**
  → `upload` → Hugging Face Hub:

**Professor Elena Rossi**
  → `visit` → our London office

**Professor James Thornton's group**
  → `share` → print

**Project Atlas Update

Marcus Rivera**
  → `present` → the latest progress on Project Atlas

**Research Collaboration with MIT CSAIL

Emily Zhang**
  → `report` → the partnership with MIT's Computer Science and Artificial
Intelligence Laboratory (CSAIL)

**Robert Kim**
  → `approve` → a total hiring budget of $2.4M for Q1-Q2 across all AI teams

**Root**
  → `cause` → The CoreWeave team (contact:

**Root cause**
  → `trace` → the Nexus-Instruct-v3 dataset

**Sarah Chen**
  → `keynote` → the World AI Summit in Amsterdam

**Scale AI**
  → `deliver` → 48,200 preference pairs (96.4% of contracted volume)

**She**
  → `recommend` → a
two-pass filtering approach: first pass for genuine toxicity, second pass
for factual calibration

**The EU AI
Act enforcement**
  → `begin` → ## 4

**The model**
  → `generate` → plausible-sounding but fabricated citations

**The team**
  → `migrate` → the core inference engine from TensorFlow

**Tomás Herrera**
  → `start` → DPO training

**Validation perplexity on the Pile**
  → `drop` → 18.2

**math validation
loss**
  → `drop` → 2,000 steps

**models.nexus.internal/meridian/7b-v1-base

Post-training plan**
  → `agree` → Carlos Mendez:
1

**our MMLU scores**
  → `lag` → expectations

**our compliance team in Dublin**
  → `flag` → three risk areas in the Atlas pipeline

**that**
  → `reduce` → our model
size
  → `contradict` → some of our safety assumptions

**the "red-teaming then
revise" loop**
  → `do` → at least 3 diverse evaluator personas

**the SFT training on 32 GPUs**
  → `hit` → an OOM (Out of Memory) error at batch
size 8 with sequence length 4096

**the automatic recovery**
  → `corrupt` → the optimizer state

**the math subset**
  → `pull` → mathematical content

**the new ONNX export pipeline**
  → `work` → staging at the Berlin datacenter

**the node**
  → `have` → a failing
  cooling fan assembly

**we**
  → `score` → 34.2%

## Most Mentioned Entities (Top 15)

| Rank | Entity | Label | Mentions |
|------|--------|-------|----------|
| 1 | 1 | Topic | 2 |
| 2 | 2 | Topic | 2 |
| 3 | 3 | Topic | 2 |
| 4 | 4 | Topic | 2 |
| 5 | 5 | Topic | 2 |
| 6 | Amsterdam | Location | 2 |
| 7 | GPU | Organization | 2 |
| 8 | Nexus Technologies | Organization | 2 |
| 9 | Toronto | Location | 2 |
| 10 | ## 2 | Topic | 1 |
| 11 | $2.4M | Topic | 1 |
| 12 | 0.1 | Topic | 1 |
| 13 | 0.3 | Topic | 1 |
| 14 | 0.3% | Topic | 1 |
| 15 | 0.5 | Topic | 1 |

---
*End of ontology report.*
