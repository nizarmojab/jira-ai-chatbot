# Jira AI Chatbot

AI-powered Jira assistant for automotive delivery teams. The project combines Jira Cloud, OpenAI tool calling, a terminal chatbot, and a Flask web UI to turn natural-language questions into actionable project insights.

## What This Project Does

- Search Jira issues in French or English without writing JQL manually
- Analyze tickets, blockers, dependencies, comments, and sprint health
- Expose Jira capabilities to the LLM through structured tools
- Provide two interfaces:
  - a Rich CLI chatbot
  - a Flask web chat UI and KPI dashboard
- Seed a realistic automotive Jira dataset for demos and testing

## Project Context

- Domain: automotive software integration
- Client scenario: Stellantis
- Integrator scenario: Capgemini Engineering
- Suppliers represented in the sample data: Harman and Marelli
- Default Jira project key: `SCRUM`

## Architecture

```text
User -> CLI / Web UI -> LLM Agent -> Jira Tools -> Jira Client -> Jira Cloud
                                   -> formatted response -> UI
```

Main modules:

- `src/jira_client.py`: low-level Jira Cloud API wrapper
- `src/jira_tools.py`: tool layer exposed to OpenAI
- `src/llm_agent.py`: tool-calling agent with short-term memory
- `src/chatbot.py`: terminal chatbot
- `dashboard/chatbot_ui.py`: web chat interface
- `dashboard/dashboard.py`: live Jira KPI dashboard

More details: [docs/architecture.md](docs/architecture.md)

## Repository Structure

```text
jira-chatbot/
|-- dashboard/          # Flask UIs, static assets, templates
|-- docs/               # architecture and setup notes
|-- jira_setup/         # Jira dataset generation scripts
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

Then fill in your Jira and OpenAI credentials in `.env`.

### 3. Run the CLI chatbot

```bash
python src/chatbot.py
```

### 4. Run the web chat UI

```bash
python dashboard/chatbot_ui.py
```

Open `http://localhost:5001`

### 5. Run the KPI dashboard

```bash
python dashboard/dashboard.py
```

Open `http://localhost:5000`

## Example Queries

- `show me critical bugs`
- `quels tickets sont bloqués ?`
- `sprint report`
- `analyze SCRUM-5`
- `what blocks SCRUM-42`

## Jira Demo Data

The repository includes scripts to populate Jira with a realistic automotive project dataset:

- `jira_setup/seed_tickets.py`
- `jira_setup/enrich_tickets.py`
- `jira_setup/advanced_enrich.py`

These scripts create epics, stories, tasks, bugs, subtasks, sprint data, comments, dependencies, regression tickets, test scenarios, and technical debt items.

Important: if your Jira project is already populated, do not rerun these scripts blindly.

See: [jira_setup/README_setup.md](jira_setup/README_setup.md) and [docs/jira_setup.md](docs/jira_setup.md)

## Testing

Manual smoke-test scripts included in the repo:

- `python test_connection.py`
- `python test_jira_tool.py`
- `python test_llm_agent.py`
- `python test_chat_endpoint.py`
- `python test_simple.py`

Query scenarios:

- `python tests/test_queries.py`

## GitHub Publishing Notes

Before pushing this repository:

1. Make sure `.env` is never committed.
2. Use `.env.example` as the public template.
3. Review hardcoded URLs or organization-specific names if you want a more generic public version.
4. Add screenshots of the web UI and dashboard if you want a stronger project page.

## Security

If any real credentials were ever stored in `.env`, rotate them before publishing the repository.

## Status

The core chatbot flow is implemented, and the project is suitable for demo, iteration, and GitHub presentation. Some parts are still closer to a polished prototype than a production-hardened application.
