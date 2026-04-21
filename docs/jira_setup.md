# Jira Project Setup — Step 1 Summary

## Project: SCRUM on chatbotjira.atlassian.net

## What was created

### Tickets (306 total)

| Type | Count |
|------|-------|
| Epic | 6 |
| Story | ~60 |
| Task | ~80 |
| Bug | ~80 |
| Subtask | ~80 |

### 6 Epics

| Epic | Supplier | Domain |
|------|----------|--------|
| Vehicle Infotainment System | Harman | Software |
| Vehicle Diagnostics & Monitoring | Marelli | Integration |
| OTA Update System | Harman | Software |
| Connectivity & CAN Communication | Marelli | Hardware |
| Safety & Functional Safety (AUTOSAR) | Marelli | Safety |
| Power Management & Sleep Modes | Marelli | Hardware |

### Fix Versions

| Version | Release Date |
|---------|-------------|
| v1.0.0 - Initial Integration | 2026-02-28 |
| v1.1.0 - CAN & Diagnostics Fix | 2026-03-31 |
| v1.2.0 - OTA & Infotainment | 2026-04-30 |
| v2.0.0 - Safety & AUTOSAR | 2026-09-30 |

### Sprints

| Sprint | Velocity | Status |
|--------|----------|--------|
| Sprint 1 - CAN Foundation | 34 SP | Closed |
| Sprint 2 - OTA & Infotainment | 41 SP | Closed |
| Sprint 3 - Safety & Power | 38 SP | Closed |
| Sprint 4 - Release Prep v1.1 | — | Active |

### Components

- CAN Communication (Lead: Marelli)
- OTA Update System (Lead: Harman)
- HMI & Infotainment (Lead: Harman)
- Diagnostics & ECU (Lead: Marelli)
- Safety & Power (Lead: Marelli)

### Special tickets

- 10 Tech Debt items
- 10 Improvements
- 3 Regression tickets
- 12 Test scenarios (PASS/FAIL/BLOCKED)
- 49 Overdue tickets (intentional)
- 27 Blocked tickets

### Custom labels

`SEV1_critical` · `SEV2_major` · `BENCH_HIL01` · `BENCH_HIL03`
`BCM_0x10` · `GW_0x20` · `0x7DF` · `SW_v1.0.1`
`regression` · `tech-debt` · `overdue` · `blocked`
`test-passed` · `test-failed` · `test-blocked`

## Scripts used

| Script | Purpose |
|--------|---------|
| `seed.py` | Initial ticket generation |
| `enrich_tickets.py` | 8 enrichment improvements |
| `advanced_enrich.py` | Sprints, workflow, cascade deps |

## Dashboard

Real-time Flask dashboard running at `http://localhost:5000`
- 8 KPIs (total, critical, blocked, overdue, regressions...)
- 3 charts (status, type, components)
- 5 filtered lists