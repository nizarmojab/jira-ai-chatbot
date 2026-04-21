# Architecture — Jira AI Chatbot

## Overview

```
User input (FR/EN)
       │
       ▼
  chatbot.py          ← CLI loop + /commands dispatcher
       │
       ▼
  llm_agent.py        ← GPT-4o + Tool Use + Memory
       │
  ┌────┴────┐
  │         │
  ▼         ▼
jira_      LLM
tools.py   response
  │
  ▼
jira_client.py        ← REST API calls to Jira Cloud
  │
  ▼
formatter.py          ← Rich terminal display
```

## Data Flow

1. User types query → `chatbot.py` receives input
2. If `/command` → dispatcher handles directly
3. If natural language → `llm_agent.py` sends to GPT-4o with tools
4. GPT-4o decides which tool(s) to call
5. `jira_tools.py` executes the tools via `jira_client.py`
6. Results returned to GPT-4o for analysis/summary
7. Final response displayed by `formatter.py` using Rich

## Memory Management

```python
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user",   "content": "bugs critiques ?"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool",   "tool_call_id": "...", "content": "..."},
    {"role": "assistant", "content": "Voici les bugs critiques..."},
    # ... last MEMORY_TURNS exchanges
]
```

## Tool Use Loop

```
GPT-4o response
    │
    ├─ finish_reason = "tool_calls"
    │       │
    │       ├─ execute tool 1 → append result
    │       ├─ execute tool 2 → append result
    │       └─ call GPT-4o again with results
    │
    └─ finish_reason = "stop"
            │
            └─ return final text response
```