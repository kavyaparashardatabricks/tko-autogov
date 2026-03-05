# Finance Governance

Automated data governance for Databricks Unity Catalog. Scans your catalog, uses an LLM to classify column sensitivity, and applies tags plus access policies -- so you don't have to do it by hand.

## The Problem

Financial services teams manage hundreds of tables with thousands of columns containing sensitive data: customer PII, payment card numbers, compensation figures, session tokens. As data grows, keeping governance current becomes a losing battle:

- **New tables appear constantly** -- data engineers create tables faster than governance teams can review them.
- **Sensitive columns hide in plain sight** -- a column named `ssn` is obvious, but `field_7` containing credit scores is not.
- **Manual tagging doesn't scale** -- applying Unity Catalog tags and access policies to every column by hand is tedious and error-prone.
- **Staleness is the norm** -- even when policies are applied initially, schema changes silently introduce untagged, unprotected columns.

The result: data teams either slow down to wait for governance reviews, or move fast and accumulate compliance risk.

## The Solution

Finance Governance automates the entire lifecycle:

1. **Scan** -- Reads `information_schema.columns` across one or all catalogs to build a complete column inventory.
2. **Diff** -- Compares the current scan against a stored snapshot (in Lakebase) to identify only what changed: new columns, updated columns, deleted columns.
3. **Classify** -- Sends changed columns to a Foundation Model (Claude Sonnet 4.5 via Databricks serving) which returns sensitivity labels (`PII`, `PCI`, `CONFIDENTIAL`, `HIGHLYSENSITIVE`) with confidence scores.
4. **Apply or Suggest** -- In **Suggest** mode, shows recommendations in the UI. In **Agent** mode, executes `ALTER TABLE` statements to set Unity Catalog tags, column masks, row filters, and time-based access controls.
5. **Remember** -- Persists the column snapshot to Lakebase so subsequent runs only re-classify genuinely new or changed columns, keeping LLM costs proportional to actual schema drift.

All runs are recorded in an audit trail with full before/after details.

### What Gets Applied (Agent Mode)

| Sensitivity | Tag Value | Policy |
|-------------|-----------|--------|
| PII (name, email, SSN, phone, DOB, address, IP) | `sensitivity = PII` | Column mask: value replaced with `***REDACTED***` for non-admin users |
| PCI (card number, CVV, expiry, cardholder name) | `sensitivity = PII` | Column mask (same as above) |
| Confidential (salary, revenue, balance, credit score) | `sensitivity = CONFIDENTIAL` | Row filter: restricts row access to members of selected workspace groups |
| Time-sensitive (session tokens, OTP, temp credentials) | `sensitivity = HIGHLYSENSITIVE` | Row filter: access limited to business hours (UTC 08:00-17:00, Mon-Fri) |

## Architecture

```
Frontend (React)  -->  FastAPI Backend  -->  Databricks Workspace
                            |                   - Unity Catalog (scan + tag)
                            |                   - SQL Warehouse (execute statements)
                            |                   - Foundation Model (classify)
                            |                   - SCIM Groups (RBAC)
                            v
                        Lakebase (PostgreSQL)
                            - column_memory (snapshot for diffing)
                            - run_trail (audit log)
                            - classification_results (model outputs)
                            - notification_candidates (deferred alerts)
```

The app runs as a Databricks App with its own service principal. The service principal needs admin-level privileges on the catalogs it governs.

## Quick Start

### Prerequisites

- Databricks workspace with Unity Catalog, a SQL Warehouse, and the `databricks-claude-sonnet-4-5` Foundation Model endpoint
- Databricks CLI v0.230+
- Node.js 18+ (for building the frontend)

### Deploy

```bash
# 1. Build the frontend
cd frontend && npm install && npm run build && cd ..

# 2. Authenticate
databricks auth login --host https://<your-workspace-url>

# 3. Create a Lakebase database (the app auto-creates its tables)
#    Do this via the Databricks UI: Catalog > Databases > Create

# 4. Create and deploy the app
databricks apps create finance-governance \
  --description "Unity Catalog governance automation"

databricks apps deploy finance-governance \
  --source-code-path .
```

Then attach a Lakebase database resource to the app in the UI and redeploy.

### First Run

1. Open the app URL
2. Select a catalog (or "All catalogs")
3. Choose **Suggest** mode for a dry run, or **Agent** mode to apply changes
4. In Agent mode, select workspace groups for RBAC row filters
5. Click **Run Scan**

### Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set connection variables (or create a .env file)
export DATABRICKS_HOST=https://<workspace-url>
export DATABRICKS_TOKEN=<your-pat>
export PGHOST=<lakebase-host>
export PGPORT=5432
export PGDATABASE=<db-name>
export PGUSER=<your-email>

# Backend
uvicorn app:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm run dev
```

## Seed Data

The `seed_data.sql` file creates 7 tables in a `trial` catalog that cover all sensitivity categories:

| Table | Sensitivity |
|-------|------------|
| `customers` | PII (name, email, phone, SSN, DOB, address) |
| `payment_methods` | PCI (card number, CVV, expiry, cardholder name) |
| `transactions` | PCI + Confidential (amounts, card refs) |
| `employee_compensation` | Confidential (salary, bonus, equity) |
| `session_tokens` | Time-sensitive (bearer tokens, OTP, refresh tokens) |
| `accounts` | PII + Confidential (account numbers, balances) |
| `loan_applications` | PII + PCI + Confidential (SSN, income, credit score) |

Run it against a SQL Warehouse before your first scan to have meaningful data to classify.

## Project Structure

```
├── app.py                  # FastAPI entry point + SPA serving
├── app.yaml                # Databricks App deployment config
├── requirements.txt        # Python dependencies
├── seed_data.sql           # Demo tables for all sensitivity types
├── server/
│   ├── config.py           # Databricks SDK + OAuth helpers
│   ├── db.py               # Lakebase async layer (asyncpg)
│   ├── routes/             # API endpoints
│   └── governance/
│       ├── pipeline.py     # Orchestration: scan -> diff -> classify -> apply
│       ├── scan.py         # Unity Catalog column scanner
│       ├── diff.py         # Memory-based change detection
│       ├── classify.py     # LLM sensitivity classifier (swappable)
│       ├── tags_policies.py# Tag + mask + filter application
│       └── groups.py       # Workspace group discovery
├── frontend/               # React + Vite + TypeScript + Tailwind
│   └── src/
│       ├── App.tsx
│       ├── api.ts          # Typed HTTP client
│       └── components/     # Header, SetupPanel, RunButton, Results, Trail
├── jobs/
│   └── governance_scan.py  # Entrypoint for scheduled Databricks Jobs
└── docs/
    ├── architecture.md     # Pipeline, data model, and component diagrams
    ├── quickstart.md       # Step-by-step setup guide
    └── configuration.md    # Environment variable reference
```

## Design Decisions

**Incremental by default** -- The diff engine stores a fingerprint per column in Lakebase. Subsequent scans only send genuinely new or changed columns to the LLM, keeping inference costs low even on large catalogs.

**Swappable classifier** -- The `classify.py` module defines a `BaseClassifier` ABC. The current implementation calls a Databricks Foundation Model endpoint, but a fine-tuned model endpoint can be dropped in by implementing a new subclass and changing `get_classifier()`.

**Suggest before Agent** -- The two-mode design lets admins preview what would happen before committing. The same pipeline runs in both modes; only the apply step is gated.

**Deferred notifications** -- PII/PCI findings are stored in a `notification_candidates` table with `status = pending`. Email delivery can be wired up later without changing the pipeline.

**Single workspace scope** -- The app authenticates to one workspace (via the Databricks App service principal or local credentials). Multi-workspace support can be added by parameterizing the workspace identity.
