#!/usr/bin/env python3
"""
config.py
=========
Central configuration module for Jira Multi-Agent Chatbot.
Loads all environment variables and provides validation.
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    """Application configuration from environment variables."""

    # ── Jira Configuration ────────────────────────────────
    JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")
    JIRA_ACCOUNT_ID = os.getenv("JIRA_ACCOUNT_ID", "")

    # ── LLM Configuration ─────────────────────────────────
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # ── Application Settings ──────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    MAX_RESULTS = int(os.getenv("MAX_RESULTS", "25"))
    MEMORY_TURNS = int(os.getenv("MEMORY_TURNS", "10"))

    @classmethod
    def validate_jira(cls) -> tuple[bool, str]:
        """
        Validate Jira configuration.

        Returns:
            (is_valid, error_message)
        """
        if not cls.JIRA_BASE_URL:
            return False, "❌ JIRA_BASE_URL is not set in .env"

        if not cls.JIRA_EMAIL:
            return False, "❌ JIRA_EMAIL is not set in .env"

        if not cls.JIRA_API_TOKEN:
            return False, "❌ JIRA_API_TOKEN is not set in .env"

        return True, "OK Jira configuration is valid"

    @classmethod
    def validate_llm(cls) -> tuple[bool, str]:
        """
        Validate LLM configuration (at least one API key).

        Returns:
            (is_valid, error_message)
        """
        if not cls.ANTHROPIC_API_KEY and not cls.OPENAI_API_KEY:
            return False, "❌ No LLM API key found (ANTHROPIC_API_KEY or OPENAI_API_KEY)"

        if cls.ANTHROPIC_API_KEY:
            return True, "OK Anthropic API key configured"
        else:
            return True, f"OK OpenAI API key configured (model: {cls.OPENAI_MODEL})"

    @classmethod
    def validate_all(cls) -> tuple[bool, list[str]]:
        """
        Validate all configuration.

        Returns:
            (is_valid, messages)
        """
        messages = []
        all_valid = True

        jira_valid, jira_msg = cls.validate_jira()
        messages.append(jira_msg)
        if not jira_valid:
            all_valid = False

        llm_valid, llm_msg = cls.validate_llm()
        messages.append(llm_msg)
        if not llm_valid:
            all_valid = False

        return all_valid, messages


# Export singleton instance
config = Config()
