# Jira AI Chatbot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#quick-start)
[![Flask](https://img.shields.io/badge/Flask-Web%20UI-black.svg)](#project-surfaces)
[![OpenAI](https://img.shields.io/badge/OpenAI-Tool%20Calling-10a37f.svg)](#architecture)
[![Jira Cloud](https://img.shields.io/badge/Jira-Cloud-0052CC.svg)](#project-overview)

AI-powered Jira assistant for automotive delivery teams. This project connects Jira Cloud with OpenAI tool calling to let users explore tickets, blockers, sprint status, and project health in natural language through a CLI chatbot, a web chat UI, and a live dashboard.

## Project Overview

This repository was designed around a realistic automotive integration scenario:

- Client context: Stellantis
- Engineering context: Capgemini Engineering
- Suppliers represented in the sample dataset: Harman and Marelli
- Main Jira project key: `SCRUM`
- Languages supported in practice: French and English

The goal is simple: turn Jira from a manual JQL-heavy workflow into a conversational assistant that can search, analyze, summarize, and surface operational insights faster.

## Key Features

- Natural-language Jira queries in French or English
- OpenAI tool-calling agent connected to Jira actions and read operations
- Rich CLI experience with formatted issue tables and panels
- Flask web chat interface for conversational ticket exploration
- Real-time Jira dashboard with KPIs, charts, blocked work, regressions, and sprint data
- Jira dataset generation scripts for realistic demos and testing
- Support for ticket details, dependencies, comments, worklogs, project metadata, and sprint health

## Project Surfaces

### 1. CLI chatbot

Terminal-based assistant powered by `Rich`:

- natural-language questions
- slash commands like `/jql`, `/issue`, `/sprint`, `/my`
- structured output for issue lists and ticket details

### 2. Web chat UI

Flask app with:

- modern chat layout
- local chat history in the browser
- quick query cards
- connection health check

Run with:

```bash
python dashboard/chatbot_ui.py
```

Open: `http://localhost:5001`

### 3. KPI dashboard

Flask dashboard focused on project visibility:

- total tickets
- critical bugs
- blocked items
- overdue work
- regressions
- tech debt
- sprint snapshots
- charts by type, status, and component

Run with:

```bash
python dashboard/dashboard.py
```

Open: `http://localhost:5000`

## Architecture

```text
User
  |
  +--> CLI / Web UI / Dashboard
            |
            +--> LLM Agent
                    |
                    +--> Jira Tool Layer
                            |
                            +--> Jira Client
                                    |
                                    +--> Jira Cloud REST API
```

Core modules:

- `src/jira_client.py`: Jira Cloud REST wrapper
- `src/jira_tools.py`: tool definitions and tool execution layer
- `src/llm_agent.py`: OpenAI-powered agent with tool calls and memory
- `src/chatbot.py`: terminal chatbot entrypoint
- `src/formatter.py`: Rich output formatting
- `dashboard/chatbot_ui.py`: Flask chat UI backend
- `dashboard/dashboard.py`: Flask KPI dashboard backend

Additional architecture notes: [docs/architecture.md](docs/architecture.md)

## Repository Structure

```text
jira-chatbot/
|-- dashboard/          # Flask UIs, templates, JS, CSS, images
|-- docs/               # architecture and setup notes
|-- jira_setup/         # Jira dataset generation and enrichment scripts
|-- src/                # chatbot core
|-- tests/              # query scenarios and support tests
|-- test_*.py           # manual smoke tests
|-- .env.example        # safe environment template
|-- requirements.txt
`-- README.md
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Then fill in your Jira and OpenAI credentials.

### 3. Run the CLI chatbot

```bash
python src/chatbot.py
```

### 4. Run the web chat UI

```bash
python dashboard/chatbot_ui.py
```

### 5. Run the dashboard

```bash
python dashboard/dashboard.py
```

## Environment Variables

See [`.env.example`](.env.example).

Main values:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Optional values:

- `LOG_LEVEL`
- `MAX_RESULTS`
- `MEMORY_TURNS`
- `DRY_RUN`

## Example Queries

- `show me critical bugs`
- `quels tickets sont bloques ?`
- `sprint report`
- `analyze SCRUM-5`
- `what blocks SCRUM-42`
- `show me my assigned issues`

## Demo Data and Jira Seeding

The repository includes scripts to generate a realistic Jira project dataset for demos:

- `jira_setup/seed_tickets.py`
- `jira_setup/enrich_tickets.py`
- `jira_setup/advanced_enrich.py`

These scripts populate Jira with:

- epics
- stories
- tasks
- bugs
- subtasks
- comments and worklogs
- dependencies and blocker chains
- sprints and roadmap signals
- regression tickets
- test scenarios
- tech debt and improvement backlog

Important: do not rerun them blindly on a Jira project that already contains data.

More details:

- [jira_setup/README_setup.md](jira_setup/README_setup.md)
- [docs/jira_setup.md](docs/jira_setup.md)

## Testing

Manual smoke tests:

- `python test_connection.py`
- `python test_jira_tool.py`
- `python test_llm_agent.py`
- `python test_chat_endpoint.py`
- `python test_simple.py`

Query scenarios:

- `python tests/test_queries.py`

## Screenshots

You can improve the GitHub page further by adding screenshots in a `docs/screenshots/` folder and linking them here, for example:

```md
![Web Chat UI](docs/screenshots/chat-ui.png)
![Dashboard](docs/screenshots/dashboard.png)
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## Security

- Never commit `.env`
- Always use `.env.example` as the public template
- If real credentials were ever exposed locally, rotate them before making the repository public

## License

This repository is released under the [MIT License](LICENSE).
