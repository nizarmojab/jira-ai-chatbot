# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

AI-powered chatbot that converts natural language (French/English) to Jira queries using GPT-4o Tool Use.

**Domain Context**: Automotive software integration project
- Client: Stellantis  
- Integrator: Capgemini Engineering  
- Suppliers: Harman (software) · Marelli (hardware)  
- Jira: SCRUM project with 306 tickets (bugs, stories, epics, tasks)

**Stack**: Python 3.10+ · OpenAI GPT-4o · Jira REST API v3 · Rich (terminal UI) · Flask (dashboard)

---

## Development Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env  # Then edit with real credentials

# Run chatbot (main app - NOT YET IMPLEMENTED)
python src/chatbot.py

# Run dashboard (IMPLEMENTED)
python dashboard/dashboard.py  # → http://localhost:5000

# Seed Jira with test tickets (IMPLEMENTED)
python jira_setup/seed_tickets.py
DRY_RUN=true python jira_setup/seed_tickets.py  # test mode

# Enrich tickets with realistic content (IMPLEMENTED)
python jira_setup/enrich_tickets.py
python jira_setup/advanced_enrich.py

# View test queries
python tests/test_queries.py  # prints 20 test queries to CLI

# Test specific component (once implemented)
python -c "from src.jira_client import JiraClient; print(JiraClient().search('project=SCRUM'))"
```

---

## Architecture: Data Flow

```
User input (FR/EN natural language)
    │
    ▼
chatbot.py                     ← CLI loop, command dispatcher
    │
    ├─ /commands → direct JQL execution
    │
    └─ NL query → llm_agent.py  ← GPT-4o + Tool Use
                       │
                       ├─> decides which tools to call
                       │
                       ▼
                  jira_tools.py     ← 12 tools (search, get_issue, etc.)
                       │
                       ▼
                  jira_client.py    ← Jira REST API wrapper
                       │
                       ▼
                  [Jira Cloud API]
                       │
                       ▼ results
                  llm_agent.py      ← analyzes + summarizes
                       │
                       ▼
                  formatter.py      ← Rich tables/panels
                       │
                       ▼
                  Terminal display
```

**Key Insight**: The LLM (GPT-4o) doesn't generate JQL directly. It *selects* which Jira tools to call based on the user's intent, executes them, then summarizes the results in natural language.

---

## Core Components (Implementation Status)

### ✅ **Fully Implemented**
- [dashboard/dashboard.py](dashboard/dashboard.py) — Flask web dashboard with real-time Jira KPIs
- [jira_setup/seed_tickets.py](jira_setup/seed_tickets.py) — Generates 200+ realistic automotive tickets
- [jira_setup/enrich_tickets.py](jira_setup/enrich_tickets.py) — Adds rich descriptions/comments
- [tests/test_queries.py](tests/test_queries.py) — 20 NLP test cases with expected JQL
- [docs/architecture.md](docs/architecture.md) — Detailed architecture diagram

### 🚧 **Planned (Not Yet Implemented)**
- [src/chatbot.py](src/chatbot.py) — Main CLI loop (entry point)
- [src/llm_agent.py](src/llm_agent.py) — GPT-4o agent with tool use + memory
- [src/jira_tools.py](src/jira_tools.py) — 12 Jira tools exposed to LLM
- [src/jira_client.py](src/jira_client.py) — Jira API wrapper with pagination
- [src/formatter.py](src/formatter.py) — Rich terminal output formatter

---

## The 12 Jira Tools

Each tool = 1 Python function + OpenAI Tool JSON schema. GPT-4o selects which to call based on user intent.

| Tool | Purpose | Example Query |
|------|---------|---------------|
| `search_issues(jql)` | JQL search → list of tickets | "critical bugs" |
| `get_issue(key)` | Full ticket details | "analyze SCRUM-5" |
| `get_epic_tree(epic_key)` | Epic → stories → subtasks | "show epic SCRUM-42" |
| `get_dependencies(key)` | Links (blocks, relates to) | "what blocks SCRUM-5" |
| `get_sprint_info()` | Active sprint status | "sprint report" |
| `get_project_info()` | Project metadata | "list components" |
| `get_my_issues()` | Current user's tickets | "my tickets" |
| `get_components()` | Component list | N/A |
| `get_versions()` | Fix versions/releases | N/A |
| `get_comments(key)` | Ticket comments | N/A |
| `open_in_jira(key)` | Opens browser | "open SCRUM-5" |
| `get_worklogs(key)` | Time tracking | N/A |

**Implementation Note**: Each tool must include a clear `description` field — GPT-4o uses these to decide which tools to call.

---

## OpenAI Tool Use Pattern

The chatbot uses OpenAI's function calling (Tool Use) pattern:

1. **Send message + tool definitions** → GPT-4o  
2. **GPT-4o responds** with `tool_calls` array (or plain text)  
3. **Execute each tool** → get results  
4. **Append results** to conversation with `role: "tool"`  
5. **Send back to GPT-4o** → it analyzes and responds in natural language  

**Critical**: Conversation history must include all messages (user, assistant, tool results) to maintain context. Keep last `MEMORY_TURNS` exchanges (default: 10).

See [docs/architecture.md:40-63](docs/architecture.md) for detailed flow diagram.

---

## Jira API Specifics

**Pagination**: Jira Cloud 2025+ uses `nextPageToken`, NOT `startAt`:
```python
payload = {"jql": "...", "maxResults": 100}
response = requests.post(f"{base_url}/rest/api/3/search/jql", json=payload, auth=auth)
next_token = response.json().get("nextPageToken")
if next_token:
    payload["nextPageToken"] = next_token
```

**Search Endpoint**: Use `/rest/api/3/search/jql` (POST), not `/rest/api/3/search` (GET).

**Description Format**: Jira uses ADF (Atlassian Document Format), not Markdown. Convert accordingly when updating descriptions.

**Sprint API**: `/rest/agile/1.0/board/{board_id}/sprint` — Board ID for SCRUM project: 1

---

## Custom Claude Code Commands

This repo defines 4 custom [/.claude/commands](.claude/commands/):

1. **`/jira-search <query>`** — Natural language → Jira search
   - Maps NL to JQL (e.g., "blocked" → `status = Blocked`)
   - Displays Rich table with clickable URLs
   - See [.claude/commands/jira-search.md](.claude/commands/jira-search.md)

2. **`/jira-analyze <KEY>`** — Deep ticket analysis
   - Fetches ticket + dependencies + comments
   - GPT-4o generates health score (0-100) + recommendations
   - See [.claude/commands/jira-analyze.md](.claude/commands/jira-analyze.md)

3. **`/jira-report <type>`** — Generate reports
   - Types: `sprint` | `standup` | `release` | `blockers`
   - Uses GPT-4o to analyze project state
   - See [.claude/commands/jira-report.md](.claude/commands/jira-report.md)

4. **`/jira-update <KEY> <action>`** — Update tickets
   - **ALWAYS confirm before writing to Jira**
   - Actions: change priority, status, assignee, improve description
   - See [.claude/commands/jira-update.md](.claude/commands/jira-update.md)

---

## Environment Variables

Required in [.env](.env):
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your.email@domain.com
JIRA_API_TOKEN=your_token_here
JIRA_PROJECT_KEY=SCRUM
JIRA_ACCOUNT_ID=712020:...  # for assignee operations

OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o

# Optional
LOG_LEVEL=INFO
MAX_RESULTS=25
MEMORY_TURNS=10
```

**Never commit .env** — it's in .gitignore.

---

## Test Queries

[tests/test_queries.py](tests/test_queries.py) contains 20 bilingual test cases:

**Search**: "show me critical bugs" · "quels tickets sont bloqués ?" · "bugs in CAN component"  
**Analysis**: "analyze SCRUM-5" · "what is blocking the sprint ?"  
**Actions**: "improve description of SCRUM-42" · "change priority of SCRUM-5 to High"  
**Reports**: "sprint report" · "prepare standup"  

Run after implementing the chatbot to validate NLP → Jira translation.

---

## Implementation Rules

When implementing the core components ([src/](src/)):

1. **Jira Pagination**: Use `nextPageToken` (not `startAt`)
2. **Error Handling**: Catch JiraError, OpenAI errors, network timeouts
3. **Type Hints**: All functions must have type hints
4. **Rich Output**: Never use plain `print()` — always use Rich (Table, Panel, Tree)
5. **Tool Descriptions**: Write clear tool descriptions — GPT-4o uses them to select tools
6. **Memory Management**: Keep last `MEMORY_TURNS` exchanges in conversation history
7. **Logging**: Use `logging` module (not print) for debug output
8. **Environment Variables**: Never hardcode credentials — always use os.getenv()

---

## Project Structure

```
jira-chatbot/
├── CLAUDE.md                  ← this file
├── .env                       ← credentials (gitignored)
├── requirements.txt
├── README.md
├── .claude/
│   └── commands/              ← custom /jira-* commands
│       ├── jira-search.md
│       ├── jira-analyze.md
│       ├── jira-report.md
│       └── jira-update.md
├── src/                       ← main chatbot (TO BE IMPLEMENTED)
│   ├── chatbot.py
│   ├── llm_agent.py
│   ├── jira_tools.py
│   ├── jira_client.py
│   └── formatter.py
├── jira_setup/                ← Jira data generation (DONE)
│   ├── seed_tickets.py
│   ├── enrich_tickets.py
│   └── advanced_enrich.py
├── dashboard/                 ← Flask web UI (DONE)
│   └── dashboard.py
├── tests/
│   └── test_queries.py
└── docs/
    ├── architecture.md
    └── jira_setup.md
```
