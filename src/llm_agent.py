#!/usr/bin/env python3
"""
llm_agent.py
============
GPT-4o agent with OpenAI Tool Use for Jira queries.

The agent:
1. Receives natural language query
2. Decides which Jira tools to call
3. Executes tools and gets results
4. Analyzes results and responds in natural language

Maintains conversation history for context.
"""
from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI
from dotenv import load_dotenv

from .jira_tools import JIRA_TOOLS_SCHEMAS, JIRA_TOOLS_MAP

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MEMORY_TURNS = int(os.getenv("MEMORY_TURNS", "10"))

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env")


class JiraAgent:
    """
    GPT-4o agent with Tool Use for Jira chatbot.

    Features:
    - Natural language → tool selection
    - Multi-turn tool execution
    - Conversation memory
    - Bilingual (FR/EN)
    """

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.conversation_history: List[Dict[str, Any]] = []
        self.system_prompt = self._build_system_prompt()

        logger.info(f"JiraAgent initialized with model {self.model}")

    def _build_system_prompt(self) -> str:
        """Build system prompt for the agent."""
        return """Tu es un assistant IA spécialisé dans la gestion de tickets Jira pour un projet automobile (Stellantis × Capgemini Engineering).

**Ton rôle** :
- Répondre aux questions sur les tickets Jira en langage naturel (FR/EN)
- Utiliser les outils Jira disponibles pour récupérer les informations
- Analyser les données et fournir des insights pertinents
- Être concis mais précis

**Contexte projet** :
- Projet : SCRUM (Infotainment & Connectivity)
- Client : Stellantis
- Intégrateur : Capgemini Engineering
- Fournisseurs : Harman (software), Marelli (hardware)

**Outils disponibles** :
- `search_issues` : Recherche JQL (ex: "project = SCRUM AND status = Blocked")
- `get_issue` : Détails complets d'un ticket
- `get_epic_tree` : Epic + stories + subtasks
- `get_dependencies` : Liens entre tickets (blocks, is blocked by)
- `get_sprint_info` : Rapport de sprint actif
- `get_project_info` : Métadonnées du projet
- `get_my_issues` : Tickets de l'utilisateur
- `get_components` : Liste des composants
- `get_versions` : Versions/releases
- `get_comments` : Commentaires d'un ticket
- `open_in_jira` : Ouvrir dans le navigateur
- `get_worklogs` : Temps passé

**Instructions** :
1. Identifie l'intention de l'utilisateur
2. Sélectionne le(s) outil(s) approprié(s)
3. Analyse les résultats
4. Réponds en français ou anglais (selon la langue de la question)
5. Sois concis : 2-3 phrases + données structurées

**Exemples de queries** :
- "show me critical bugs" → `search_issues("project = SCRUM AND issuetype = Bug AND priority = Highest")`
- "what blocks SCRUM-5" → `get_dependencies("SCRUM-5")`
- "sprint report" → `get_sprint_info()`
- "analyze SCRUM-42" → `get_issue("SCRUM-42")` + `get_dependencies("SCRUM-42")`

Commence !"""

    def process_query(self, user_message: str) -> Dict[str, Any]:
        """
        Process user query and return response.

        Args:
            user_message: User's natural language query

        Returns:
            {
                "response": "Natural language response",
                "tickets": [...],  # Optional
                "jql": "...",      # Optional
                "metadata": {...}  # Optional
            }
        """
        logger.info(f"Processing query: {user_message}")

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        # Keep only last MEMORY_TURNS exchanges
        self._trim_history()

        # Call GPT-4o with tools
        response = self._call_openai()

        # Process response (may include tool calls)
        result = self._process_response(response)

        logger.info(f"Response generated: {len(result['response'])} chars")
        return result

    def _call_openai(self) -> Any:
        """
        Call OpenAI API with conversation history and tools.

        Returns:
            OpenAI response object
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history,
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=JIRA_TOOLS_SCHEMAS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2000,
            )
            return response

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _process_response(self, response: Any) -> Dict[str, Any]:
        """
        Process OpenAI response (handle tool calls).

        Args:
            response: OpenAI response object

        Returns:
            Result dict
        """
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        logger.info(f"Response received - finish_reason: {finish_reason}")
        logger.info(f"Has tool_calls: {hasattr(message, 'tool_calls')}")
        if hasattr(message, "tool_calls") and message.tool_calls:
            logger.info(f"Number of tool_calls: {len(message.tool_calls)}")

        # Add assistant message to history
        self.conversation_history.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": message.tool_calls if hasattr(message, "tool_calls") else None,
        })

        # If no tool calls, return text response
        if finish_reason == "stop" or not message.tool_calls:
            return {
                "response": message.content or "No response generated.",
                "tickets": [],
                "jql": None,
                "metadata": {},
            }

        # Execute tool calls
        logger.info(f"Executing {len(message.tool_calls)} tool calls")
        tool_results = []

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            logger.info(f"Calling tool: {tool_name}({tool_args})")

            # Execute tool
            tool_function = JIRA_TOOLS_MAP.get(tool_name)
            if not tool_function:
                result = {"error": f"Tool {tool_name} not found"}
            else:
                try:
                    logger.info(f"Executing {tool_name} with args: {tool_args}")
                    result = tool_function(**tool_args)
                    logger.info(f"Tool {tool_name} returned: {type(result)} - {result}")

                    # Ensure result is not None
                    if result is None:
                        logger.error(f"Tool {tool_name} returned None!")
                        result = {"success": False, "error": "Tool returned None"}

                except Exception as e:
                    logger.error(f"Tool execution error: {e}", exc_info=True)
                    result = {"error": str(e)}

            # Add tool result to history
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

            tool_results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })

        # Call GPT-4o again with tool results to get final response
        final_response = self._call_openai()
        final_message = final_response.choices[0].message

        # Add final assistant message to history
        self.conversation_history.append({
            "role": "assistant",
            "content": final_message.content,
        })

        # Extract tickets and JQL from tool results
        tickets = []
        jql = None

        for tool_result in tool_results:
            result_data = tool_result["result"]
            if result_data and isinstance(result_data, dict):
                if "issues" in result_data:
                    tickets.extend(result_data["issues"])
                if "jql" in result_data:
                    jql = result_data["jql"]

        return {
            "response": final_message.content or "Analysis complete.",
            "tickets": tickets,
            "jql": jql,
            "metadata": {
                "tools_used": [tr["tool"] for tr in tool_results],
                "tool_count": len(tool_results),
            },
        }

    def _trim_history(self) -> None:
        """
        Keep only last MEMORY_TURNS exchanges in history.
        Each exchange = user message + assistant response + tool calls.
        """
        # Count user messages
        user_messages = [msg for msg in self.conversation_history if msg["role"] == "user"]

        if len(user_messages) > MEMORY_TURNS:
            # Find index of (MEMORY_TURNS+1)th user message from the end
            cutoff_index = None
            user_count = 0

            for i in range(len(self.conversation_history) - 1, -1, -1):
                if self.conversation_history[i]["role"] == "user":
                    user_count += 1
                    if user_count == MEMORY_TURNS + 1:
                        cutoff_index = i
                        break

            if cutoff_index is not None:
                self.conversation_history = self.conversation_history[cutoff_index + 1:]
                logger.info(f"Trimmed history to {MEMORY_TURNS} turns")

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def get_history_length(self) -> int:
        """Get number of messages in history."""
        return len(self.conversation_history)


# ─────────────────────────────────────────────────────
#  Convenience function for single queries
# ─────────────────────────────────────────────────────
_global_agent: Optional[JiraAgent] = None


def process_query(user_message: str, agent: Optional[JiraAgent] = None) -> Dict[str, Any]:
    """
    Process a single query (convenience function).

    Args:
        user_message: User query
        agent: Optional agent instance (creates new one if None)

    Returns:
        Result dict
    """
    global _global_agent

    if agent is None:
        if _global_agent is None:
            _global_agent = JiraAgent()
        agent = _global_agent

    return agent.process_query(user_message)
