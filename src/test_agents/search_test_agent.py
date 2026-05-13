#!/usr/bin/env python3
"""
search_test_agent.py
====================
Dedicated test agent for SearchAgent.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.agents.search_agent import SearchAgent
from src.jira_client import JiraError
from src.test_agents.base_test_agent import BaseTestAgent


class _FakeChoiceMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeChoiceMessage(content)


class _FakeOpenAIResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, jql_by_prompt: Dict[str, str], error_by_prompt: Dict[str, Exception] | None = None):
        self.jql_by_prompt = jql_by_prompt
        self.error_by_prompt = error_by_prompt or {}

    def create(self, model: str, temperature: float, max_tokens: int, messages: List[Dict[str, str]]):
        user_prompt = messages[-1]["content"]
        for natural_query, error in self.error_by_prompt.items():
            if natural_query in user_prompt:
                raise error
        for natural_query, jql in self.jql_by_prompt.items():
            if natural_query in user_prompt:
                return _FakeOpenAIResponse(jql)
        return _FakeOpenAIResponse("project = SCRUM ORDER BY updated DESC")


class _FakeChat:
    def __init__(self, jql_by_prompt: Dict[str, str], error_by_prompt: Dict[str, Exception] | None = None):
        self.completions = _FakeChatCompletions(jql_by_prompt, error_by_prompt)


class FakeOpenAIClient:
    """
    Minimal OpenAI-compatible fake used by SearchTestAgent.
    """

    def __init__(self, jql_by_prompt: Dict[str, str], error_by_prompt: Dict[str, Exception] | None = None):
        self.chat = _FakeChat(jql_by_prompt, error_by_prompt)


class FakeJiraClient:
    """
    Minimal Jira-compatible fake used by SearchTestAgent.
    """

    def __init__(self, project_key: str = "SCRUM"):
        self.project_key = project_key
        self.search_results: Dict[str, Dict[str, Any]] = {}
        self.error_by_jql: Dict[str, Exception] = {}

    def register_search_result(self, jql: str, issues: List[Dict[str, Any]], total: int | None = None) -> None:
        self.search_results[jql] = {
            "issues": issues,
            "total": len(issues) if total is None else total,
            "jql": jql,
        }

    def register_search_error(self, jql: str, error: Exception) -> None:
        self.error_by_jql[jql] = error

    def search_issues(self, jql: str, fields: List[str] | None = None, max_results: int | None = None) -> Dict[str, Any]:
        if jql in self.error_by_jql:
            raise self.error_by_jql[jql]
        return self.search_results.get(
            jql,
            {"issues": [], "total": 0, "jql": jql},
        )


class SearchTestAgent(BaseTestAgent):
    """
    Test agent responsible for validating SearchAgent behavior.
    """

    def __init__(self):
        super().__init__("SearchTestAgent", "SearchAgent")

    def run(self) -> Dict[str, Any]:
        """
        Run a compact test suite against SearchAgent using mocks only.
        """
        results = [
            self._test_english_blocked_query(),
            self._test_french_critical_bug_query(),
            self._test_sanitize_jql_prefix_and_backticks(),
            self._test_project_scope_is_added_when_missing(),
            self._test_process_returns_simplified_tickets(),
            self._test_process_uses_issue_count_when_total_is_inconsistent(),
            self._test_process_handles_empty_results(),
            self._test_process_handles_empty_llm_output(),
            self._test_process_handles_openai_error(),
            self._test_process_handles_jira_error(),
        ]
        return self._build_summary(results)

    def _build_agent(
        self,
        jql_by_prompt: Dict[str, str],
        jira_client: FakeJiraClient,
        error_by_prompt: Dict[str, Exception] | None = None,
    ) -> SearchAgent:
        return SearchAgent(
            jira_client=jira_client,
            openai_client=FakeOpenAIClient(jql_by_prompt, error_by_prompt),
            openai_model="gpt-4o",
        )

    def _test_english_blocked_query(self) -> Dict[str, Any]:
        query = "show me all blocked tickets"
        expected_jql = 'project = SCRUM AND status = Blocked ORDER BY updated DESC'
        jira_client = FakeJiraClient()
        agent = self._build_agent({query: expected_jql}, jira_client)

        actual_jql = agent._convert_to_jql(query, context=[])

        return {
            "name": "english_blocked_query_to_jql",
            "success": actual_jql == expected_jql,
            "details": {
                "query": query,
                "expected_jql": expected_jql,
                "actual_jql": actual_jql,
            },
        }

    def _test_french_critical_bug_query(self) -> Dict[str, Any]:
        query = "montre-moi les bugs critiques"
        expected_jql = 'project = SCRUM AND issuetype = Bug AND priority = Highest ORDER BY priority DESC, updated DESC'
        jira_client = FakeJiraClient()
        agent = self._build_agent({query: expected_jql}, jira_client)

        actual_jql = agent._convert_to_jql(query, context=[])

        return {
            "name": "french_critical_bug_query_to_jql",
            "success": actual_jql == expected_jql,
            "details": {
                "query": query,
                "expected_jql": expected_jql,
                "actual_jql": actual_jql,
            },
        }

    def _test_sanitize_jql_prefix_and_backticks(self) -> Dict[str, Any]:
        query = "show me open tasks"
        model_output = '`JQL: project = SCRUM AND status = "To Do" ORDER BY created DESC`'
        expected_jql = 'project = SCRUM AND status = "To Do" ORDER BY created DESC'
        jira_client = FakeJiraClient()
        agent = self._build_agent({query: model_output}, jira_client)

        actual_jql = agent._convert_to_jql(query, context=[])

        return {
            "name": "sanitize_jql_prefix_and_backticks",
            "success": actual_jql == expected_jql,
            "details": {
                "query": query,
                "actual_jql": actual_jql,
            },
        }

    def _test_project_scope_is_added_when_missing(self) -> Dict[str, Any]:
        query = "show me in progress bugs"
        model_output = 'issuetype = Bug AND status = "In Progress" ORDER BY updated DESC'
        expected_jql = 'project = SCRUM AND (issuetype = Bug AND status = "In Progress" ORDER BY updated DESC)'
        jira_client = FakeJiraClient()
        agent = self._build_agent({query: model_output}, jira_client)

        actual_jql = agent._convert_to_jql(query, context=[])

        return {
            "name": "project_scope_is_added_when_missing",
            "success": actual_jql == expected_jql,
            "details": {
                "query": query,
                "actual_jql": actual_jql,
            },
        }

    def _test_process_returns_simplified_tickets(self) -> Dict[str, Any]:
        query = "show me all blocked tickets"
        jql = 'project = SCRUM AND status = Blocked ORDER BY updated DESC'
        issues = [
            {
                "key": "SCRUM-5",
                "fields": {
                    "summary": "Cold boot CAN issue",
                    "status": {"name": "Blocked"},
                    "priority": {"name": "Highest"},
                    "assignee": {"displayName": "Mohamed Nizar Mojab"},
                },
            },
            {
                "key": "SCRUM-8",
                "fields": {
                    "summary": "OTA retry flow broken",
                    "status": {"name": "Blocked"},
                    "priority": {"name": "High"},
                    "assignee": None,
                },
            },
        ]

        jira_client = FakeJiraClient()
        jira_client.register_search_result(jql, issues)
        agent = self._build_agent({query: jql}, jira_client)

        result = agent.process(query, context=[])
        returned_issues = result["data"]["issues"] if result["data"] else []
        correct_shape = all(
            sorted(issue.keys()) == ["assignee", "key", "priority", "status", "summary"]
            for issue in returned_issues
        )

        return {
            "name": "process_returns_simplified_tickets",
            "success": result["success"] and result["data"]["total"] == 2 and correct_shape,
            "details": {
                "message": result["message"],
                "total": result["data"]["total"] if result["data"] else None,
                "issues": returned_issues,
            },
        }

    def _test_process_uses_issue_count_when_total_is_inconsistent(self) -> Dict[str, Any]:
        query = "show me all blocked tickets"
        jql = 'project = SCRUM AND status = Blocked ORDER BY updated DESC'
        issues = [
            {
                "key": "SCRUM-10",
                "fields": {
                    "summary": "Blocked story",
                    "status": {"name": "Blocked"},
                    "priority": {"name": "High"},
                    "assignee": None,
                },
            }
        ]

        jira_client = FakeJiraClient()
        jira_client.register_search_result(jql, issues, total=0)
        agent = self._build_agent({query: jql}, jira_client)

        result = agent.process(query, context=[])

        return {
            "name": "process_uses_issue_count_when_total_is_inconsistent",
            "success": result["success"] and result["data"]["total"] == 1 and result["message"] == "Found 1 ticket(s).",
            "details": {
                "message": result["message"],
                "total": result["data"]["total"] if result["data"] else None,
            },
        }

    def _test_process_handles_empty_results(self) -> Dict[str, Any]:
        query = "montre-moi les bugs critiques"
        jql = 'project = SCRUM AND issuetype = Bug AND priority = Highest ORDER BY priority DESC, updated DESC'
        jira_client = FakeJiraClient()
        jira_client.register_search_result(jql, [])
        agent = self._build_agent({query: jql}, jira_client)

        result = agent.process(query, context=[])

        return {
            "name": "process_handles_empty_results",
            "success": result["success"] and result["message"] == "No tickets found." and result["data"]["issues"] == [],
            "details": {
                "message": result["message"],
                "total": result["data"]["total"] if result["data"] else None,
            },
        }

    def _test_process_handles_empty_llm_output(self) -> Dict[str, Any]:
        query = "show me all blocked tickets"
        jira_client = FakeJiraClient()
        agent = self._build_agent({query: ""}, jira_client)

        result = agent.process(query, context=[])

        return {
            "name": "process_handles_empty_llm_output",
            "success": (not result["success"]) and "empty JQL query" in result["error"],
            "details": {
                "message": result["message"],
                "error": result["error"],
            },
        }

    def _test_process_handles_openai_error(self) -> Dict[str, Any]:
        query = "montre-moi les bugs critiques"
        jira_client = FakeJiraClient()
        agent = self._build_agent(
            {},
            jira_client,
            error_by_prompt={query: RuntimeError("OpenAI timeout")},
        )

        result = agent.process(query, context=[])

        return {
            "name": "process_handles_openai_error",
            "success": (not result["success"]) and "OpenAI timeout" in result["error"],
            "details": {
                "message": result["message"],
                "error": result["error"],
            },
        }

    def _test_process_handles_jira_error(self) -> Dict[str, Any]:
        query = "show me all blocked tickets"
        jql = 'project = SCRUM AND status = Blocked ORDER BY updated DESC'
        jira_client = FakeJiraClient()
        jira_client.register_search_error(jql, JiraError("Jira search failed"))
        agent = self._build_agent({query: jql}, jira_client)

        result = agent.process(query, context=[])

        return {
            "name": "process_handles_jira_error",
            "success": (not result["success"]) and "Jira search failed" in result["error"],
            "details": {
                "message": result["message"],
                "error": result["error"],
            },
        }
