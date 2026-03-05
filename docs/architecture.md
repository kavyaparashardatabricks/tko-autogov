# Architecture

Finance Governance is a full-stack Databricks App composed of a **FastAPI backend**, a **React frontend**, and a **Lakebase (managed PostgreSQL) database** for persistent state. The backend communicates with Databricks workspace APIs to scan Unity Catalog metadata, classify column sensitivity with a Foundation Model, and optionally enforce governance policies.

## System Overview

```mermaid
graph TB
    subgraph "Databricks App"
        FE["React SPA<br/>(Vite + Tailwind)"]
        API["FastAPI Backend<br/>(uvicorn :8000)"]
    end

    subgraph "Databricks Workspace"
        UC["Unity Catalog<br/>information_schema"]
        WH["SQL Warehouse"]
        LLM["Foundation Model Endpoint<br/>(Claude Sonnet 4.5)"]
        GRP["Workspace Groups<br/>(SCIM)"]
    end

    LB["Lakebase<br/>(PostgreSQL)"]

    FE -- "/api/*" --> API
    API -- "Statement Execution API" --> WH
    WH -- "Query" --> UC
    API -- "OpenAI-compatible API" --> LLM
    API -- "SDK groups.list()" --> GRP
    API -- "asyncpg (SSL)" --> LB
```

## Governance Pipeline

Every run follows a five-stage pipeline. Only new and updated columns are sent to the LLM, keeping costs proportional to actual schema drift.

```mermaid
flowchart LR
    A["1. Scan"] --> B["2. Diff"]
    B --> C["3. Classify"]
    C --> D["4. Suggest /<br/>Apply"]
    D --> E["5. Persist<br/>Memory"]

    style A fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style B fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style C fill:#1e3a5f,stroke:#3b82f6,color:#fff
    style D fill:#4a2520,stroke:#f97316,color:#fff
    style E fill:#1e3a5f,stroke:#3b82f6,color:#fff
```

### Stage Details

| Stage | Module | What Happens |
|-------|--------|--------------|
| **Scan** | `server/governance/scan.py` | Queries `information_schema.columns` via a SQL warehouse. Builds a record per column with a SHA-256 fingerprint of its metadata (catalog, schema, table, name, type, comment). |
| **Diff** | `server/governance/diff.py` | Loads the stored `column_memory` from Lakebase and compares fingerprints. Produces three buckets: **new**, **updated**, and **deleted** columns. |
| **Classify** | `server/governance/classify.py` | Sends new + updated columns (in batches of 60) to the Foundation Model endpoint. The LLM returns sensitivity labels (`pii`, `pci`, `confidential`, `time_sensitive`, `public`) with confidence scores. |
| **Suggest / Apply** | `server/governance/tags_policies.py` | In **Suggest** mode, recommendations are returned to the UI. In **Agent** mode, the pipeline executes `ALTER TABLE` statements to apply tags, column masks, row filters, and time-based filters. |
| **Persist Memory** | `server/db.py` | Upserts the full current snapshot into `column_memory` so the next run only re-classifies genuinely changed columns. |

## Classification Flow

```mermaid
sequenceDiagram
    participant P as Pipeline
    participant S as scan.py
    participant D as diff.py
    participant C as classify.py
    participant LLM as Foundation Model
    participant DB as Lakebase

    P->>S: scan_columns(catalog)
    S-->>P: column records + fingerprints
    P->>DB: load_memory(catalog)
    DB-->>P: stored memory
    P->>D: compute_diff(current, memory)
    D-->>P: DiffResult (new, updated, deleted)
    P->>C: classify(new + updated)
    loop Batches of 60
        C->>LLM: column metadata prompt
        LLM-->>C: JSON [{column_name, labels, confidence}]
    end
    C-->>P: ColumnClassification[]
    P->>DB: insert_classifications()
    P->>DB: upsert_memory()
```

## Agent Mode — Policy Application

When the pipeline runs in Agent mode, the following governance actions are applied via SQL:

```mermaid
flowchart TD
    CLS["Classification Results"] --> PII{"Labels include<br/>pii or pci?"}
    CLS --> CONF{"Labels include<br/>confidential?"}
    CLS --> TIME{"Labels include<br/>time_sensitive?"}

    PII -- Yes --> TAG1["SET TAGS<br/>sensitivity = pii/pci"]
    PII -- Yes --> MASK["SET MASK<br/>mask_sensitive()"]

    CONF -- Yes --> TAG2["SET TAGS<br/>sensitivity = confidential"]
    CONF -- Yes --> ROW["SET ROW FILTER<br/>row_access_filter()"]

    TIME -- Yes --> TAG3["SET TAGS<br/>sensitivity = time_sensitive"]
    TIME -- Yes --> TBRF["SET ROW FILTER<br/>is_business_hours()"]
```

### UDF Details

The pipeline bootstraps a `governance_udfs` schema in each scanned catalog containing:

| UDF | Purpose |
|-----|---------|
| `mask_sensitive(val STRING)` | Returns the original value for members of `data_governance_admins`; otherwise returns `***REDACTED***` |
| `is_business_hours()` | Returns `true` during UTC 08:00–17:00, Monday–Friday |
| `row_access_filter()` | Returns `true` for members of `data_governance_admins` or any of the selected workspace groups |

## Data Model

```mermaid
erDiagram
    column_memory {
        TEXT table_catalog PK
        TEXT table_schema PK
        TEXT table_name PK
        TEXT column_name PK
        TEXT data_type
        TEXT column_comment
        TEXT fingerprint
        TIMESTAMPTZ last_seen_at
    }

    run_trail {
        TEXT run_id PK
        TIMESTAMPTZ started_at
        TIMESTAMPTZ finished_at
        TEXT catalogs
        TEXT mode
        JSONB changes_detected
        JSONB suggestions
        JSONB applied
        TEXT notification_status
    }

    classification_results {
        SERIAL id PK
        TEXT run_id FK
        TEXT table_catalog
        TEXT table_schema
        TEXT table_name
        TEXT column_name
        JSONB predicted_labels
        REAL confidence
        TEXT model_name
        TEXT model_version
        TIMESTAMPTZ created_at
    }

    notification_candidates {
        SERIAL id PK
        TEXT run_id FK
        TEXT column_fqn
        JSONB labels
        TEXT status
        TIMESTAMPTZ created_at
    }

    run_trail ||--o{ classification_results : "run_id"
    run_trail ||--o{ notification_candidates : "run_id"
```

## Frontend Components

```mermaid
graph TD
    App["App.tsx"]
    App --> Header["Header"]
    App --> Setup["SetupPanel"]
    App --> Run["RunButton"]
    App --> Results["Results"]
    App --> Trail["Trail"]

    Setup -- "GET /api/catalogs" --> CatAPI["/api/catalogs"]
    Setup -- "GET /api/groups" --> GrpAPI["/api/groups"]
    Run -- "POST /api/run" --> RunAPI["/api/run"]
    Trail -- "GET /api/trail" --> TrailAPI["/api/trail"]
```

| Component | Responsibility |
|-----------|---------------|
| **Header** | Application title and branding |
| **SetupPanel** | Catalog selector dropdown, Suggest/Agent mode toggle, workspace group checkboxes (Agent mode only) |
| **RunButton** | Triggers the pipeline via `POST /api/run`; shows spinner while running |
| **Results** | Displays scan stats, diff counts, color-coded classification badges, suggested/applied actions |
| **Trail** | Audit log of past runs with diff summaries and action counts |

## Project Layout

```
.
├── app.py                     # FastAPI entry point + SPA serving
├── app.yaml                   # Databricks App deployment config
├── requirements.txt           # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Root component + state management
│   │   ├── api.ts             # Typed HTTP client for /api/*
│   │   ├── main.tsx           # React DOM entry
│   │   ├── index.css          # Tailwind base styles
│   │   └── components/
│   │       ├── Header.tsx
│   │       ├── SetupPanel.tsx
│   │       ├── RunButton.tsx
│   │       ├── Results.tsx
│   │       └── Trail.tsx
│   ├── package.json
│   └── vite.config.ts
├── server/
│   ├── config.py              # Databricks SDK + OAuth helpers
│   ├── db.py                  # Lakebase async layer (asyncpg)
│   ├── routes/
│   │   ├── runs.py            # POST /api/run, GET /api/runs
│   │   ├── catalogs.py        # GET /api/catalogs
│   │   ├── trail.py           # GET /api/trail
│   │   └── groups.py          # GET /api/groups
│   └── governance/
│       ├── pipeline.py        # Orchestration: scan → diff → classify → apply
│       ├── scan.py            # Unity Catalog column scanner
│       ├── diff.py            # Memory diffing
│       ├── classify.py        # LLM sensitivity classifier
│       ├── tags_policies.py   # Tag + mask + filter application
│       └── groups.py          # Workspace group listing
└── docs/
    ├── architecture.md        # This file
    ├── quickstart.md          # Setup and first-run guide
    └── configuration.md       # Environment and app.yaml reference
```
