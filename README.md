# Provenance

**An evidence-bound governance auditor for DataHub lineage chains.**

Provenance answers a question no dashboard in your stack can: *can you trust this number?*

It walks the full upstream lineage of an asset, audits governance at every hop, computes a trust score where **every deduction is bound to a verifiable DataHub metadata fact**, and writes the verdict back into the catalog as a first-class tag — so the next person, or the next agent, inherits the finding.

---

## The problem

A VP opens a Power BI dashboard showing quarterly revenue. Behind it sit 13 upstream datasets across Snowflake, dbt, and S3. Some carry PII. Some have no owner. Some are undocumented.

Nobody can see this. Lineage is browsable one hop at a time, and governance metadata lives on each node separately. Answering "is this dashboard trustworthy?" by hand means opening 13 tabs and cross-referencing ownership, classification, and incident health manually — for one asset.

## What Provenance found in a real catalog

Running across 8 assets in the DataHub showcase catalog:

| Asset | Platform | Grade | Score | Upstream | Findings |
|---|---|---:|---:|---:|---:|
| Customer Analytics Measures | Power BI | F | 23/100 | 13 | 4 |
| Geographic Measures | Power BI | F | 23/100 | 13 | 4 |
| order_details | Looker | F | 23/100 | 13 | 4 |
| ORDER_DETAILS | Snowflake | D | 45/100 | 23 | 3 |
| orders | Snowflake | D | 51/100 | 1 | 4 |
| CUSTOMERS | Snowflake | C | 70/100 | 0 | 2 |
| PRODUCTS | Snowflake | C | 70/100 | 0 | 2 |
| WAREHOUSES | Snowflake | C | 70/100 | 0 | 2 |

**The BI layer scores worst.** The dashboards executives actually look at are the least trustworthy assets in the catalog, because they inherit every governance gap upstream. That inversion — where trust decreases as you move toward the business — is invisible without walking the chain.

A representative finding on ORDER_DETAILS, itself tagged Certified and GDPR:
[CRITICAL] Unowned sensitive data upstream (-40)
11 upstream nodes carry sensitive classifications with no assigned owner
Evidence:
- CUSTOMERS :: owner_count=0, glossary=PII,SOC2 Auditable
- ADDRESSES :: owner_count=0, glossary=PII
- ORDERS :: owner_count=0, glossary=PII,Order Total
A SOC2-auditable PII table with no accountable owner, feeding a certified asset. That is an audit failure, found automatically, with the evidence attached.

---

## How it works
1. **Resolve** — the target asset is resolved by name through the DataHub MCP `search` tool. URNs are never hand-constructed.
2. **Walk** — `get_lineage` is called recursively upstream, deduplicating visited nodes, to a configurable hop depth. This traversal is **fully deterministic**: no LLM is involved in deciding which node to visit next.
3. **Extract** — every node in the chain is batch-fetched via `get_entities`, and only the governance-relevant fields are retained: ownership and roles, glossary terms, tags, incident health, documentation presence, domain.
4. **Score** — six weighted checks produce a 0–100 score and letter grade. Each deduction carries the node and the exact metadata fact that caused it.
5. **Write back** — the grade is emitted to DataHub as a `Provenance-Grade-X` tag with a description explaining its basis, making the agent's verdict queryable catalog knowledge.

## The scoring rubric

| Check | Max penalty | What it detects |
|---|---|---|
| Unowned sensitive data upstream | -40 | PII / SOC2 / GDPR-classified nodes with no assigned owner |
| Ownership coverage | -20 | Proportion of the chain lacking any owner |
| No upstream lineage recorded | -20 | Provenance cannot be verified at all |
| Documentation coverage | -15 | Undocumented nodes in the chain |
| Upstream incident health | -25 | Non-passing health status anywhere upstream |
| Data steward on sensitive asset | -10 | Sensitive root with no steward role assigned |

Grades: A ≥90 TRUSTED · B ≥75 ACCEPTABLE · C ≥60 NEEDS REVIEW · D ≥40 AT RISK · F <40 NOT TRUSTWORTHY

## Setup

Requires a running DataHub instance and Python 3.10+.

```bash
pip install acryl-datahub mcp-server-datahub mcp
export DATAHUB_GMS_URL=http://localhost:8080
export DATAHUB_GMS_TOKEN=          # blank for local DataHub Core

python walker.py order_details     # walk lineage  -> audit.json
python score.py                    # score it      -> report.json / report.txt
python writeback.py                # tag DataHub, verify in graph
python batch.py                    # audit many assets -> catalog_summary.json
```

Sample outputs are in [`examples/`](examples/) — you can evaluate the results without running anything.

---

## Design decisions

**Deterministic traversal, not agentic wandering.** A language model does not decide which lineage node to visit next. Graph traversal is code. This makes audits reproducible, fast, and cheap — and means the same asset always produces the same score. The model's role is confined to interpreting the user's target and summarising findings; the findings themselves are arithmetic over metadata.

**Every deduction is bound to evidence.** No finding is asserted without the node URN and the specific metadata fact that produced it. A score you cannot audit is a score you cannot act on. This is the core contract: the report is checkable line by line against DataHub itself.

**Extraction before reasoning.** A single `get_entities` response for one node is ~18,000 characters. A 23-node chain would be over 400KB — unusable as model context and expensive to process. Provenance extracts only the governance-relevant fields at the point of retrieval, reducing each node to a compact fact record.

**"Unverifiable" is not "trustworthy".** An asset with no recorded lineage cannot be given a clean bill of health simply because there is nothing to inspect. Provenance applies an explicit penalty for absent provenance, because silence is not evidence of safety.

**The audit contributes back.** Reading a catalog is useful once. Writing the verdict back makes it durable — the grade becomes a browsable, filterable tag that the next person or agent inherits without re-running anything.

## Operational notes for self-hosted DataHub

Findings from building against DataHub Core v1.5.0.6 that may help others:

- **`DatahubRestEmitter` can silently no-op.** It accepts a metadata change proposal and reports success while writing nothing, because it uses the asynchronous batch endpoint. `DataHubGraph.emit()` uses the synchronous path and persists reliably. All write-back in Provenance goes through `DataHubGraph`, and each write is verified by reading the aspect back.
- **OpenSearch will OOM under rapid sequential search.** Running eight audits back-to-back on an 8GB host killed the OpenSearch container, after which every search returned a 500. Provenance paces its queries between audits.
- **Resolve URNs, never construct them.** URNs copied from a browser address bar are percent-encoded and will not match. Every URN in Provenance comes from a `search` result.
- **The showcase catalog carries no freshness timestamps.** This is why Provenance audits governance rather than staleness — the product follows the metadata that actually exists.

## Built with

DataHub MCP Server · DataHub Python SDK · Python 3.12 · DataHub Core v1.5.0.6

Licensed under Apache 2.0.
