#!/usr/bin/env python3
"""
orchestrator.py
===============
Central router that analyzes user messages, detects intent,
routes to appropriate agent, and maintains conversation memory.
"""
import re
from typing import Dict, List, Literal
from config import config


IntentType = Literal["SEARCH", "ANALYZE", "UPDATE", "REPORT", "DEDUP", "NOTIFY", "UNKNOWN"]


class Orchestrator:
    """
    Central orchestrator for multi-agent Jira chatbot.

    Responsibilities:
    - Detect user intent from natural language
    - Route to appropriate specialized agent
    - Maintain conversation memory (10 turns)
    - Provide context to agents
    """

    def __init__(self):
        """Initialize orchestrator with empty memory."""
        self.memory: List[Dict[str, str]] = []
        self.max_memory_turns = config.MEMORY_TURNS

    def process_message(self, user_message: str) -> Dict[str, any]:
        """
        Process user message: detect intent, route to agent, update memory.

        Args:
            user_message: Natural language query from user

        Returns:
            {
                "intent": IntentType,
                "agent": str,
                "context": List[Dict],  # Recent conversation history
                "message": str          # User message
            }
        """
        # 1. Detect intent
        intent = self._detect_intent(user_message)

        # 2. Route to agent
        agent = self._route_to_agent(intent)

        # 3. Get conversation context
        context = self._get_context()

        # 4. Add user message to memory
        self._add_to_memory("user", user_message)

        # 5. Return routing decision
        return {
            "intent": intent,
            "agent": agent,
            "context": context,
            "message": user_message
        }

    def add_assistant_response(self, response: str) -> None:
        """
        Add assistant response to memory.

        Args:
            response: Agent's response text
        """
        self._add_to_memory("assistant", response)

    def _detect_intent(self, message: str) -> IntentType:
        """
        Detect user intent from message using keyword patterns.

        Priority order: UPDATE > DEDUP > NOTIFY > REPORT > ANALYZE > SEARCH
        (Specific actions before general queries)

        Args:
            message: User message (French or English)

        Returns:
            IntentType: SEARCH, ANALYZE, UPDATE, REPORT, DEDUP, NOTIFY, or UNKNOWN
        """
        message_lower = message.lower()

        # 1. UPDATE patterns (highest priority - action verbs)
        update_patterns = [
            r'\b(update|change|modify|edit|set)\b',
            r'\b(modifie|change|met [aà] jour)\b',
            r'\b(improve|am[eé]liore|fix|corrige)\b.*\b(description|titre|title)\b',
        ]
        # Strong UPDATE signals: action verb + field name
        update_fields = r'\b(priority|priorit[eé]|priorite|status|statut|assignee|assign[eé]|description)\b'

        # Exclude NOTIFY verbs from triggering UPDATE
        notify_verbs = r'\b(send|envoie|notify|notifie|alert|alerte)\b'

        if any(re.search(pattern, message_lower) for pattern in update_patterns):
            # If action verb present, it's UPDATE (not ANALYZE)
            return "UPDATE"

        # "priority to High" but NOT "send alert to assignee"
        if re.search(update_fields, message_lower) and re.search(r'\b(to|[aà]|=)\b', message_lower):
            if not re.search(notify_verbs, message_lower):
                # Field + "to" but no notify verb → UPDATE
                return "UPDATE"

        # 2. DEDUP patterns (before SEARCH because "find" is ambiguous)
        dedup_patterns = [
            r'\b(duplicate[s]?|duplicata[s]?|doublon[s]?)\b',
            r'\b(similar|similaire[s]?)\b.*\b(ticket[s]?|issue[s]?)\b',
            r'\b(same|m[eê]me[s]?)\b.*\b(ticket[s]?|issue[s]?)\b',
            r'\b(merge|fusionn?e)\b'
        ]
        if any(re.search(pattern, message_lower) for pattern in dedup_patterns):
            return "DEDUP"

        # 3. NOTIFY patterns (before SEARCH because "send" is ambiguous)
        notify_patterns = [
            r'\b(notify|notifie|notifier)\b',
            r'\b(alert[e]?|alerte[r]?)\b',
            r'\b(warn|avertis|avertir)\b',
            r'\b(remind|rappelle|rappeler)\b',
            r'\b(send|envoie|envoyer)\b.*(message|email|notification|alert)',
            r'\b(inform|informe|informer)\b',
        ]
        if any(re.search(pattern, message_lower) for pattern in notify_patterns):
            return "NOTIFY"

        # 4. REPORT patterns (before ANALYZE)
        report_patterns = [
            r'\b(report|rapport)\b',
            r'\b(summary|r[eé]sum[eé])\b',
            r'\b(standup|daily|release|sprint)\b.*(report|rapport|summary|r[eé]sum[eé])',
            r'\b(generate|g[eé]n[eèé]re|create|cr[eé]e|prepare|pr[eé]pare)\b.*(report|rapport|standup|daily)',
            r'\b(overview|vue d\'ensemble)\b'
        ]
        if any(re.search(pattern, message_lower) for pattern in report_patterns):
            return "REPORT"

        # 5. ANALYZE patterns (specific analysis keywords)
        analyze_patterns = [
            r'\b(analyz[e]?|analyse[r]?)\b',
            r'\b(inspect|examine|investigate)\b',
            r'\b(what is blocking|qu\'?est-ce qui bloque|pourquoi)\b',
            r'\b(dependencies|d[eé]pendances)\b',
            r'\b(health|sant[eé])\b',
            r'\b(why|pourquoi|comment)\b',
        ]
        # Check for ticket key pattern (SCRUM-123) with analyze intent
        if re.search(r'[A-Z]+-\d+', message_lower):
            if any(re.search(pattern, message_lower) for pattern in analyze_patterns):
                return "ANALYZE"
            # Ticket key alone with no search words → likely analyze
            if not re.search(r'\b(find|list|show|search|affiche|liste|cherche)\b', message_lower):
                return "ANALYZE"

        if any(re.search(pattern, message_lower) for pattern in analyze_patterns):
            return "ANALYZE"

        # 6. SEARCH patterns (lowest priority - catch-all for queries)
        search_patterns = [
            r'\b(search|find|list|show|get)\b',
            r'\b(affiche|cherche|trouve|liste|montre)\b',
            r'\b(bugs?|tickets?|issues?|stories?|epics?|tasks?)\b',
            r'\b(critical|bloqu[eé]|urgent|high priority)\b',
            r'\b(component|version|sprint|assignee)\b',
            r'\b(all|tous|toutes)\b.*(tickets?|issues?|bugs?)',
        ]
        if any(re.search(pattern, message_lower) for pattern in search_patterns):
            return "SEARCH"

        return "UNKNOWN"

    def _route_to_agent(self, intent: IntentType) -> str:
        """
        Route intent to appropriate agent.

        Args:
            intent: Detected intent type

        Returns:
            Agent name (e.g., "SearchAgent", "AnalyzeAgent")
        """
        routing_map = {
            "SEARCH": "SearchAgent",
            "ANALYZE": "AnalyzeAgent",
            "UPDATE": "UpdateAgent",
            "REPORT": "ReportAgent",
            "DEDUP": "DedupAgent",
            "NOTIFY": "NotifyAgent",
            "UNKNOWN": "SearchAgent"  # Default fallback
        }
        return routing_map[intent]

    def _get_context(self) -> List[Dict[str, str]]:
        """
        Get recent conversation context.

        Returns:
            List of recent messages (up to max_memory_turns)
        """
        return self.memory.copy()

    def _add_to_memory(self, role: str, content: str) -> None:
        """
        Add message to memory and trim to max_memory_turns.

        Args:
            role: "user" or "assistant"
            content: Message content
        """
        self.memory.append({
            "role": role,
            "content": content
        })

        # Trim memory to last N turns (1 turn = user + assistant pair)
        # Each turn = 2 messages, so max_memory_turns * 2 messages
        max_messages = self.max_memory_turns * 2
        if len(self.memory) > max_messages:
            self.memory = self.memory[-max_messages:]

    def clear_memory(self) -> None:
        """Clear all conversation memory."""
        self.memory = []

    def get_memory_summary(self) -> str:
        """
        Get human-readable memory summary.

        Returns:
            Formatted string showing conversation history
        """
        if not self.memory:
            return "[Empty Memory]"

        lines = [f"[Memory: {len(self.memory)} messages, {len(self.memory)//2} turns]"]
        for msg in self.memory:
            role_label = "USER" if msg["role"] == "user" else "ASSISTANT"
            content_preview = msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
            lines.append(f"  [{role_label}] {content_preview}")

        return "\n".join(lines)
