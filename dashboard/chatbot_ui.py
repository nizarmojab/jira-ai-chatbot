#!/usr/bin/env python3
"""
chatbot_ui.py
=============
Modern web chat interface for Jira AI Chatbot.
Style: Jira/Atlassian design system.

Usage:
    python dashboard/chatbot_ui.py
    → http://localhost:5001
"""
from __future__ import annotations

import os
import sys
import logging
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

# Add parent directory to path to import src modules (once implemented)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Flask app with template and static folders
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')


# ──────────────────────────────────────────────
#  Import chatbot components
# ──────────────────────────────────────────────
try:
    from src.llm_agent import process_query
    from src.jira_client import JiraClient
    jira_client = JiraClient()
    CHATBOT_AVAILABLE = True
    logger.info("✓ Chatbot modules loaded successfully")
except ImportError as e:
    CHATBOT_AVAILABLE = False
    logger.warning(f"Chatbot modules not found: {e} — using mock responses")


# ──────────────────────────────────────────────
#  Mock response generator (remove when real chatbot is ready)
# ──────────────────────────────────────────────
def mock_chatbot_response(message: str) -> Dict[str, Any]:
    """Simulates chatbot response until real implementation is ready."""
    message_lower = message.lower()

    # Mock responses based on keywords
    if "blocked" in message_lower:
        return {
            "response": "Here are the blocked tickets in SCRUM project:",
            "tickets": [
                {
                    "key": "SCRUM-5",
                    "summary": "CAN bus initialization fails on cold boot",
                    "status": "Blocked",
                    "priority": "Highest",
                    "assignee": "Marelli Team",
                },
                {
                    "key": "SCRUM-42",
                    "summary": "OTA update fails with SSL certificate error",
                    "status": "Blocked",
                    "priority": "High",
                    "assignee": "Harman",
                },
                {
                    "key": "SCRUM-103",
                    "summary": "Diagnostics module crashes on ECU reset",
                    "status": "Blocked",
                    "priority": "Medium",
                    "assignee": "Capgemini",
                },
            ],
            "jql": "project = SCRUM AND status = Blocked",
            "count": 27,
        }

    elif "critical" in message_lower:
        return {
            "response": "Critical bugs (Highest priority):",
            "tickets": [
                {
                    "key": "SCRUM-7",
                    "summary": "Memory leak in CAN driver causes system crash",
                    "status": "In Progress",
                    "priority": "Highest",
                    "assignee": "Marelli",
                },
                {
                    "key": "SCRUM-15",
                    "summary": "Race condition in thread pool executor",
                    "status": "Open",
                    "priority": "Highest",
                    "assignee": "Unassigned",
                },
            ],
            "jql": "project = SCRUM AND issuetype = Bug AND priority = Highest",
            "count": 9,
        }

    elif "sprint" in message_lower:
        return {
            "response": "**Sprint 4 Status** 📊\n\n✅ Done: 18 tickets\n🔄 In Progress: 12 tickets\n🚫 Blocked: 5 tickets\n⏸️ Todo: 8 tickets\n\n**Velocity**: 42 story points (target: 45)\n**Health**: 🟡 At risk — 5 blockers need attention\n\n**Recommendations**:\n1. Resolve SCRUM-5 (blocks 3 stories)\n2. Assign SCRUM-15 to available developer\n3. Review overdue tickets (7 past due date)",
            "tickets": [],
            "jql": "project = SCRUM AND sprint in openSprints()",
            "count": 43,
        }

    elif message_lower.startswith("scrum-") or "analyze" in message_lower:
        ticket_key = "SCRUM-5" if "scrum-5" in message_lower else "SCRUM-42"
        return {
            "response": f"**Analyse de {ticket_key}**\n\n📋 **Summary**: CAN bus initialization fails on cold boot\n\n🎯 **Status**: Blocked\n⚡ **Priority**: Highest\n👤 **Assignee**: Marelli Team\n📅 **Created**: 2026-03-12\n🔗 **Blocks**: SCRUM-23, SCRUM-45, SCRUM-67\n\n**Health Score**: 🔴 35/100 (Critical issues)\n\n**Root Cause**: Hardware timing issue during CAN controller initialization sequence.\n\n**Impact**: Blocks 3 stories in current sprint — critical path blocker.\n\n**Recommendations**:\n1. Coordinate with Marelli for hardware fix\n2. Consider software workaround (retry logic)\n3. Escalate to Stellantis if not resolved in 48h",
            "tickets": [
                {
                    "key": ticket_key,
                    "summary": "CAN bus initialization fails on cold boot",
                    "status": "Blocked",
                    "priority": "Highest",
                    "assignee": "Marelli",
                }
            ],
            "jql": f"key = {ticket_key}",
            "count": 1,
        }

    else:
        return {
            "response": f"J'ai reçu votre message : \"{message}\"\n\n💡 **Commandes disponibles** :\n- `/blocked` — tickets bloqués\n- `/critical` — bugs critiques\n- `/sprint` — rapport de sprint\n- `/analyze SCRUM-XX` — analyse détaillée\n\nOu posez une question en langage naturel (FR/EN).",
            "tickets": [],
            "jql": None,
            "count": 0,
        }


# ──────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────
@app.route("/")
def index():
    """Main chat interface."""
    return render_template('index.html')


@app.route("/chat", methods=["POST"])
def chat():
    """
    Process chat message and return response.

    Request: {"message": "show me blocked tickets"}
    Response: {
        "response": "Voici les tickets bloqués...",
        "tickets": [...],
        "jql": "project = SCRUM AND status = Blocked",
        "timestamp": "2026-04-16T14:30:00"
    }
    """
    try:
        data = request.get_json()
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"error": "Empty message"}), 400

        logger.info(f"User query: {message}")

        # Use real chatbot or fallback to mock
        if CHATBOT_AVAILABLE:
            try:
                result = process_query(message)
                logger.info("✓ Real chatbot response generated")
            except Exception as e:
                logger.error(f"Chatbot error: {e}", exc_info=True)
                result = {
                    "response": f"❌ Error: {str(e)}",
                    "tickets": [],
                    "jql": None,
                }
        else:
            result = mock_chatbot_response(message)
            logger.info("Mock response generated")

        result["timestamp"] = datetime.utcnow().isoformat()

        logger.info(f"Response sent: {len(result.get('tickets', []))} tickets")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": str(e),
        }), 500


@app.route("/health", methods=["GET"])
def health():
    """
    Check Jira connection status.

    Response: {
        "jira_connected": true,
        "project": "SCRUM",
        "base_url": "https://chatbotjira.atlassian.net"
    }
    """
    try:
        jira_connected = bool(JIRA_BASE_URL and JIRA_API_TOKEN)

        # Test actual connection if chatbot available
        if CHATBOT_AVAILABLE:
            try:
                project = jira_client.get_project_info()
                jira_connected = True
            except Exception as e:
                logger.warning(f"Jira connection test failed: {e}")
                jira_connected = False

        return jsonify({
            "jira_connected": jira_connected,
            "project": PROJECT_KEY,
            "base_url": JIRA_BASE_URL,
            "chatbot_available": CHATBOT_AVAILABLE,
        })

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "jira_connected": False,
            "error": str(e),
        }), 500


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = 5001
    logger.info(f"Starting Jira AI Chatbot UI on http://localhost:{port}")
    logger.info(f"Chatbot modules available: {CHATBOT_AVAILABLE}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
    )
