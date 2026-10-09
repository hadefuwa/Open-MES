# Open-MES Build Plan, v4: generic MES layer, a low-volume electronics assembler as the reference business

## 0. Project positioning

A generic, open-source MES that any discrete manufacturer can adopt. **A low-volume electronics assembler is the worked example**: it supplies the workflows, test requirements and ERP integration needs used to shape and validate the design, but nothing business-specific is hardcoded in the core.

- **Configurable, not customised:** product types, routings, workflow states, test definitions, custom fields, downtime reasons and roles are configuration or data, not code.
- **The example business lives in `examples/electronics-assembly/`:** its routings, test templates, sample data and ERP adapter config. A second, different example (a job shop) proves the core isn't shaped around one business.
- **ERP adapters are plugins:** the core ships the adapter interface and a CSV adapter. CIM50 and Sage adapters are separate plugins that others can copy and extend.
- **Open-source hygiene:** licence chosen up front (suggest Apache-2.0, or AGPL-3.0 if you want to prevent closed hosted forks), README, CONTRIBUTING, code of conduct, issue templates, semantic versioning, changelog, public docs.
- **No confidential data in the repo:** Example sample data is anonymised or synthetic; no real customer, pricing or CIM50 credentials.

## 1. Scope

**In scope**
- The MES application: work orders, routing/operations, scheduling, serial-number traceability, quality and test records, downtime and loss logging (manual), operator and planner screens, reporting, user management, audit trail.
- ERP connectivity as a **pluggable adapter layer**, with Sage and CIM50 as candidate adapters. Secondary priority.
- AI and MCP features (optional, after the core is in use): read-only MCP server over MES data, natural-language queries, and suggested insights. Always human-approved; never in critical production logic.

**Out of scope (separate project)**
- PLCs, SCADA, OPC UA, MQTT/UNS, Node-RED, Telegraf, TimescaleDB, any machine-state or counter capture, automatic OEE.

**Design-for-later rule:** machine data arrives later as just another source of events. Keep an append-only `production_events` model with a `source` field (`operator`, `erp`, `system`, future `machine`) and a documented ingest API, so the later project can plug in without schema changes. Don't build anything machine-specific now.

## 2. Guiding decisions

| Decision | Choice | Why |
|---|---|---|
| Build order | Core workflows first, ERP adapters last | The MES must be useful standalone |
| Stack | PostgreSQL + one Python web app (Django recommended; FastAPI + React is the alternative) | Auth, roles, admin and migrations included; one language for a small team |
| Deployment | Docker Compose on one server, with backups and tested restore | |
| Auth | Microsoft 365 SSO if available, else local accounts | |
| ERP integration | Adapter interface: `import_orders`, `import_products`, `push_progress`, `push_completions`. Adapters run in a separate integration module, never through the frontend | Lets Sage and CIM50 be added without touching core |
| Keys | Store external IDs (part number, order number) with a source system on every imported record | Mapping, not redesign |
| Headline metrics | First-pass yield, lead time, WIP, rework rate, on-time delivery, downtime by reason (manual) | Fit low-volume manual assembly and test |
| Traceability | Serial numbers, build records, test results, approver are first-class from the start | Supports regulatory and customer records (example: CE Technical File) |
| Configurability | Workflow states, routings, test templates, custom fields and reason codes defined in data/config | Lets other businesses adopt without forking |
| Internationalisation | Translatable UI strings and locale-aware dates/units from day one | Cheap now, painful later |
| Licence | Decide in Phase 0 (Apache-2.0 vs AGPL-3.0); all dependencies must be compatible | |
| Extensibility | Plugin points for ERP adapters, report templates and (later) event sources | Community contributions without core changes |
| Scheduling | Manual planner board, deadline and clash warnings only | No finite-capacity optimisation |

**Open decision:** Django vs FastAPI + React, settled in Phase 0 (after the build-vs-adopt check).

## 3. Core workflow (define first)

Order created (manual or ERP import) → released → scheduled to workstation → operator starts operation → assembly → test (results against serial number) → quality approval (pass / rework / scrap) → complete → progress reported to ERP.

Every transition is an event with who, when, and source.

## 4. Data model (v1)

products, work_orders, work_order_operations, units (serial numbers), build_records, workstations, operators, production_schedule, test_results / quality_inspections, production_events (with `source`), downtime_reasons, downtime_events (manual), users/roles, audit_log, external_refs (system, entity, external_id), integration_log.

## 5. Phases

### Phase 0: Discovery and de-risking (1–2 weeks)
- Map the real order-to-ship flow, stations, test steps, defect types; choose pilot area.
- Build-vs-adopt check: half-day on Odoo Community MRP and ERPNext Manufacturing.
- Find out what Sage and CIM50 can expose (API, ODBC, file import/export) and prove one round trip for each you care about. Result decides adapter design.
- Confirm required metrics; identify operator hardware (tablets, barcode scanners); name a second code reader.
- Separate what is generic (core) from what is example-specific (example config) in the workflow; sketch a second, different example business to test the abstraction.
- Choose licence and set up the public repo basics (README, CONTRIBUTING, code of conduct).
- **Done when:** workflow signed off, pilot chosen, framework and licence chosen, ERP mechanisms known.

### Phase 1: Foundations (1–2 weeks)
- Repo, Docker Compose, CI (lint, tests), migrations, seed data.
- Auth and roles: operator, supervisor, planner, quality, admin.
- API documentation (OpenAPI) for every endpoint.
- **Done when:** `docker compose up` gives a working app with login.

### Phase 2: Work orders and traceability (2–3 weeks)
- Products, workstations, operators; work order and operation lifecycle.
- Serial numbers, build records, approver sign-off.
- Touch-friendly operator screen: large targets, high contrast, barcode input.
- Audit trail on every transition.
- **Done when:** a serialised job runs end to end with a complete traceability record.

### Phase 3: Scheduling (1–2 weeks)
- Planner board with drag-and-drop, priorities, deadline and clash warnings.
- **Done when:** a planner runs a week's schedule from the board.

### Phase 4: Quality, downtime and backups (2 weeks)
- Test result entry, pass/fail/rework/scrap with reason codes; electronic forms replacing paper; electronic work instructions (basic).
- Manual downtime and loss logging with reasons; Pareto view.
- Automated backups and a tested restore **before real data goes in**.
- **Done when:** first pilot on the floor.

### Phase 5: Reporting (1–2 weeks)
- Dashboards: first-pass yield, lead time, WIP, rework, on-time delivery, downtime Pareto.
- Export to PDF/Excel/CSV.
- Operators can flag unrealistic standard times; planners review them.
- **Done when:** figures match hand calculations for a known period.

### Phase 6: Hardening and pilot (4+ weeks, overlaps with 5)
- Permissions review, monitoring, failure tests (server restart, network drop, restore).
- Operator feedback loop; fix usability issues; expand cell by cell.

### Phase 7: ERP adapter framework (2 weeks)
- Define the adapter interface, scheduled sync runner, idempotent imports, error handling, integration log, reconciliation screen.
- Manual CSV import/export adapter as the baseline, usable with any ERP.
- **Done when:** orders import and completions export through the framework using the CSV adapter.

### Phase 8: Sage and CIM50 adapters (2–3 weeks each, as priority allows)
- Implement against the mechanisms proven in Phase 0.
- Import orders and products; push progress and completed quantities.
- **Done when:** a completed job appears correctly in the ERP without re-keying.

### Phase 9: AI and MCP (optional, after Phase 6 has real data)
- Read-only MCP server exposing MES queries (orders, schedule, traceability, quality, downtime) using a dedicated read-only DB role or the documented API, with per-user permissions and audit logging of every query.
- Use cases, in order of value: natural-language questions ("which serials failed test X this month?"), summaries of shift/week performance, spotting recurring defects or downtime reasons, drafting traceability reports.
- Suggestions only: AI never writes to orders, schedules or quality records. Any action needs a human to confirm.
- Treat MES text fields as untrusted input to the model (prompt-injection risk).
- **Done when:** a supervisor can answer a traceability question in plain English and the answer matches a manual SQL check.

## 6. Repo layout

```
Open-MES/
  app/          core MES (models, views/API, migrations, tests)
  integration/  adapter interface + csv/ adapter; sage/ and cim50/ as plugins
  mcp/          read-only MCP server (Phase 9)
  examples/
    electronics-assembly/  routings, test templates, synthetic data, ERP config
    job-shop/              second example business
  infra/        docker-compose, backup scripts
  Docs/         user guide, admin guide, schema, API, runbooks
  Docs/Archived/ superseded plans
  LICENSE, README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CHANGELOG.md
```

## 7. Risks

- **Scope creep into machines:** held out by the scope rule; only the `source` field and ingest API are prepared.
- **ERP rigidity (Sage/CIM50):** Phase 0 spike; CSV adapter as fallback.
- **Unagreed workflow:** Phase 0 gate.
- **Single maintainer:** one language, documented API, named second reader.
- **Operator adoption:** hardware and UI tested with operators at the bench.
- **Bad metrics:** validate against hand calculations; standard-time flagging.
- **Single-business-shaped design:** a second example business and a "no hardcoded example-business terms in core" check in review.
- **Over-configurability:** a configuration engine can swallow the project. Keep v1 to a small set of well-defined extension points.
- **Open-source maintenance burden:** set expectations in the README (support level, release cadence); keep the first release small.
- **Leaking confidential data:** review sample data and commits before the repo goes public.

## 8. First steps

1. Draw the workflow state diagram with production; pick the pilot area.
2. Evaluate Odoo/ERPNext (half day).
3. Sage and CIM50 data-exchange spike.
4. Decide Django vs FastAPI + React.

## Changes from v3

- Repositioned as a generic open-source MES with a low-volume electronics assembler as the reference example.
- Added configurability, i18n, licence, extensibility and open-source hygiene.
- Example-business specifics moved to `examples/electronics-assembly/`; CIM50 and Sage adapters are plugins.
- New risks: Single-business-shaped design, over-configurability, maintenance burden, data leakage.

## Changes from v2

- Removed all PLC, SCADA, MQTT, Node-RED, Telegraf, TimescaleDB and OEE-from-machines work (to a separate project). AI/MCP stays in scope as an optional Phase 9.
- Added `source` field on events and an ingest API as the future hook for machine data.
- ERP integration reframed as an adapter framework with CSV baseline, then Sage and CIM50 adapters.
- Phases reduced from 10 to 9; reporting and hardening now come before ERP.
