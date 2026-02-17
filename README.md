# Scout

Scout is an **enterprise knowledge agent** with Claude Code-like capabilities. It finds information across a local documents directory — and learns from every interaction.

## The Problem

Enterprise context is scattered. Policies in one folder, runbooks in another, decisions buried in docs nobody can find. The Knowledge Agent 1.0 approach — dump everything into a vector database — doesn't work. Chunks lose context, embeddings miss nuance, and the system never learns where things actually live.

## The Solution

Scout takes a different approach, inspired by how Claude Code navigates codebases:

- **Awareness** — Knows what sources exist and what they contain
- **Search** — Grep-like search across file contents
- **Read** — Full documents with context, never chunks
- **Learn** — Builds knowledge over time

Every interaction teaches Scout where information lives. "PTO policy isn't in the HR folder, it's in the Employee Handbook." This learning compounds over time.

## Quick Start

```sh
# Clone and setup
git clone https://github.com/agno-agi/scout.git && cd scout
cp example.env .env  # Add your OPENAI_API_KEY

# Start the application
docker compose up -d --build

# Load knowledge (inside the container)
docker compose exec scout-api python -m scout.scripts.load_knowledge
```

Confirm Scout is running at [http://localhost:8000/docs](http://localhost:8000/docs).

## Connect to the Web UI

1. Open [os.agno.com](https://os.agno.com) and login
2. Add OS → Local → `http://localhost:8000`
3. Click "Connect"

## Try It

Scout ships with sample enterprise documents. Try these queries:
```
What's our PTO policy?
→ Your PTO policy is in the Employee Handbook. You get unlimited PTO with
  manager approval, minimum 2 weeks recommended per year.

How do I deploy to production?
→ Here's the deployment process from the runbook...

What's the SLA for P1 incidents?
→ P1 incidents require acknowledgment within 15 minutes and resolution
  within 4 hours. Full incident response process in the runbook...
```

## Documents Directory

Scout browses a local `documents/` directory. Sample documents are included:

| Directory | Contents |
|-----------|----------|
| **company-docs** | HR policies, benefits guide, employee handbook, OKRs, strategy |
| **engineering-docs** | Architecture docs, deployment runbooks, incident response |
| **data-exports** | Metrics, reports, data exports |

Add your own documents to `documents/` and Scout will find them.

## The Learning Loop

```
User Question
     ↓
Search Knowledge + Learnings (Do I already know where this is?)
     ↓
Navigate: list_sources → get_metadata → search → read
     ↓
Found? → Return answer, save discovery if surprising
Not found? → Try fallback paths, save negative knowledge
```

Scout improves without retraining through two complementary systems:

| System | Stores | How It Evolves |
|--------|--------|----------------|
| **Knowledge** (curated) | Source metadata, intent routing, known patterns | Curated by you + Scout |
| **Learnings** (discovered) | Decision traces: what worked, what didn't, why | Managed automatically |

## Deploy to Railway

```sh
railway login
./scripts/railway_up.sh

# Load knowledge
railway run python -m scout.scripts.load_knowledge
```

### Manage deployment

```sh
railway logs --service scout      # View logs
railway open                      # Open dashboard
railway up --service scout -d     # Update after changes
```

## Local Development

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
docker compose up -d scout-db
python -m scout  # CLI mode
```

## Adding Knowledge

Scout works best when it understands your organization's knowledge landscape.

### Source Metadata (`scout/knowledge/sources/files.json`)
```json
{
  "source_name": "Local Files",
  "source_type": "files",
  "directories": [
    {"path": "company-docs", "description": "Company policies, HR, planning"},
    {"path": "engineering-docs", "description": "Architecture, runbooks, RFCs"},
    {"path": "data-exports", "description": "Reports and metrics"}
  ]
}
```

### Intent Routing (`scout/knowledge/routing/intents.json`)
```json
{
  "intent_mappings": [
    {
      "intent": "Find PTO or vacation policy",
      "keywords": ["pto", "vacation", "time off", "leave"],
      "known_locations": ["company-docs/policies/employee-handbook.md"]
    }
  ]
}
```

### Load Knowledge
```sh
python -m scout.scripts.load_knowledge            # Upsert
python -m scout.scripts.load_knowledge --recreate  # Fresh start
```

## Evaluations

Scout includes an evaluation suite to measure response quality across categories.

```sh
# Run all tests (string matching)
python -m scout.evals.run_evals

# Filter by category
python -m scout.evals.run_evals --category policy
python -m scout.evals.run_evals --category runbook

# LLM-based grading (uses gpt-5-mini)
python -m scout.evals.run_evals --llm-grader

# Verbose output (show full responses on failure)
python -m scout.evals.run_evals --verbose

# Source citation verification (affects pass/fail)
python -m scout.evals.run_evals --check-sources

# Combined
python -m scout.evals.run_evals -g -s -v
```

### Test Categories

| Category | Tests | What It Covers |
|----------|-------|----------------|
| **policy** | 5 | HR policies, benefits, handbook questions |
| **runbook** | 5 | Deployment, incidents, on-call operations |
| **navigation** | 4 | Multi-hop search, cross-document reasoning |
| **edge_case** | 3 | Missing docs, ambiguous queries, graceful handling |

### Adding Test Cases

Add new test cases in `scout/evals/test_cases.py`:

```python
TestCase(
    question="What is the password policy?",
    expected_strings=["14 characters", "90 days"],
    category="navigation",
    golden_path="company-docs/policies/security-policy.md",
)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `EXA_API_KEY` | No | Exa API key for web research |
| `DOCUMENTS_DIR` | No | Documents directory (default: `./documents`, `/documents` in Docker) |
| `DB_HOST` | No | Database host (default: localhost) |
| `DB_PORT` | No | Database port (default: 5432) |

## Further Reading

- [Agno Docs](https://docs.agno.com)
- [Discord](https://agno.com/discord)
