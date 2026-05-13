#!/usr/bin/env python3
"""
base_agent.py
=============
Abstract base class for all specialized agents.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseAgent(ABC):
    """
    Abstract base class for all Jira agents.

    Each agent must implement the process() method which handles
    a user message and returns a structured result.
    """

    def __init__(self, name: str):
        """
        Initialize base agent.

        Args:
            name: Agent name (e.g., "SearchAgent", "AnalyzeAgent")
        """
        self.name = name

    @abstractmethod
    def process(self, message: str, context: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Process user message with conversation context.

        Args:
            message: User's natural language query
            context: Recent conversation history from orchestrator
                     Format: [{"role": "user", "content": "..."}, ...]

        Returns:
            {
                "success": bool,
                "agent": str,              # Agent name
                "action": str,             # What the agent did
                "data": Any,               # Result data (tickets, analysis, etc.)
                "message": str,            # Human-readable response
                "error": str | None        # Error message if failed
            }
        """
        pass

    def _extract_context_value(self, context: List[Dict[str, str]], key: str) -> str | None:
        """
        Extract a value from conversation context.

        Useful for resolving references like "it", "the ticket", "that bug".

        Args:
            context: Conversation history
            key: Key to search for (e.g., "ticket_key", "component")

        Returns:
            Last mentioned value or None
        """
        # Search context in reverse (most recent first)
        for msg in reversed(context):
            if key in msg.get("content", ""):
                # Simple extraction - can be improved with regex
                return msg["content"]
        return None

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.name}>"
