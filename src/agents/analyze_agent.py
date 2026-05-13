#!/usr/bin/env python3
"""
analyze_agent.py
================
Agent for deep ticket analysis based on rules (no LLM/RAG).
"""
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from src.agents.base_agent import BaseAgent
from src.jira_client import JiraClient, JiraError


class AnalyzeAgent(BaseAgent):
    """
    Specialized agent for analyzing Jira tickets.

    Performs rule-based analysis without LLM:
    - Fetches ticket details, dependencies, comments
    - Calculates health score (0-100)
    - Generates actionable recommendations
    """

    def __init__(self, jira_client: Optional[JiraClient] = None):
        """Initialize analyze agent."""
        super().__init__("AnalyzeAgent")
        self.jira = jira_client or JiraClient()

    def process(self, message: str, context: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze a Jira ticket in depth.

        Args:
            message: Natural language query (e.g., "analyze SCRUM-5")
            context: Conversation history

        Returns:
            {
                "success": bool,
                "agent": "AnalyzeAgent",
                "action": "analyze",
                "data": {
                    "ticket_key": str,
                    "summary": str,
                    "health_score": int,
                    "analysis": {...},
                    "recommendations": [...]
                },
                "message": str,
                "error": str | None
            }
        """
        try:
            # 1. Extract ticket keys from message (support multiple)
            ticket_keys = self._extract_ticket_keys(message, context)
            if not ticket_keys:
                return {
                    "success": False,
                    "agent": self.name,
                    "action": "analyze",
                    "data": None,
                    "message": "No ticket key found. Please specify ticket(s) (e.g., 'analyze SCRUM-5' or 'analyze SCRUM-5, SCRUM-42')",
                    "error": "Missing ticket key"
                }

            # 2. Handle single vs multiple tickets
            if len(ticket_keys) == 1:
                # Single ticket: detailed analysis
                return self._analyze_single_ticket(ticket_keys[0])
            else:
                # Multiple tickets: comparative analysis
                return self._analyze_multiple_tickets(ticket_keys)

        except JiraError as e:
            return {
                "success": False,
                "agent": self.name,
                "action": "analyze",
                "data": None,
                "message": f"Failed to analyze ticket: {str(e)}",
                "error": str(e)
            }

    def _analyze_single_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """
        Analyze a single ticket in detail.

        Args:
            ticket_key: Ticket key (e.g., "SCRUM-5")

        Returns:
            Analysis result dict
        """
        try:
            # Fetch ticket data
            issue = self.jira.get_issue(ticket_key)
            links = self.jira.get_issue_links(ticket_key)
            comments = self.jira.get_comments(ticket_key)
            worklogs = self.jira.get_worklogs(ticket_key)

            # Perform analysis
            analysis = self._analyze_ticket(issue, links, comments, worklogs)

            # Calculate health score
            health_score = self._calculate_health_score(analysis)

            # Generate recommendations
            recommendations = self._generate_recommendations(analysis, health_score)

            # Build detailed response message
            fields = issue.get("fields", {})
            summary = fields.get("summary", "No summary")

            detailed_message = self._build_detailed_message(
                ticket_key, summary, health_score, analysis, recommendations
            )

            return {
                "success": True,
                "agent": self.name,
                "action": "analyze",
                "data": {
                    "ticket_key": ticket_key,
                    "summary": summary,
                    "health_score": health_score,
                    "analysis": analysis,
                    "recommendations": recommendations
                },
                "message": detailed_message,
                "error": None
            }

        except JiraError as e:
            return {
                "success": False,
                "agent": self.name,
                "action": "analyze",
                "data": None,
                "message": f"Failed to analyze {ticket_key}: {str(e)}",
                "error": str(e)
            }

    def _analyze_multiple_tickets(self, ticket_keys: List[str]) -> Dict[str, Any]:
        """
        Analyze multiple tickets and provide comparative summary.

        Args:
            ticket_keys: List of ticket keys

        Returns:
            Comparative analysis result dict
        """
        analyses = []
        failed = []

        # Analyze each ticket
        for ticket_key in ticket_keys:
            try:
                issue = self.jira.get_issue(ticket_key)
                links = self.jira.get_issue_links(ticket_key)
                comments = self.jira.get_comments(ticket_key)
                worklogs = self.jira.get_worklogs(ticket_key)

                analysis = self._analyze_ticket(issue, links, comments, worklogs)
                health_score = self._calculate_health_score(analysis)
                recommendations = self._generate_recommendations(analysis, health_score)

                fields = issue.get("fields", {})
                summary = fields.get("summary", "No summary")

                analyses.append({
                    "ticket_key": ticket_key,
                    "summary": summary,
                    "health_score": health_score,
                    "analysis": analysis,
                    "recommendations": recommendations
                })

            except JiraError as e:
                failed.append({"ticket_key": ticket_key, "error": str(e)})

        # Build comparative message
        message = self._build_comparative_message(analyses, failed)

        return {
            "success": len(analyses) > 0,
            "agent": self.name,
            "action": "analyze_multiple",
            "data": {
                "analyses": analyses,
                "failed": failed,
                "total": len(ticket_keys),
                "successful": len(analyses)
            },
            "message": message,
            "error": None if len(analyses) > 0 else "All tickets failed to analyze"
        }

    def _extract_ticket_keys(self, message: str, context: List[Dict[str, str]]) -> List[str]:
        """
        Extract ALL ticket keys from message or context.

        Args:
            message: User message
            context: Conversation history

        Returns:
            List of ticket keys (e.g., ["SCRUM-5", "SCRUM-42"])
        """
        import re

        # Look for pattern like SCRUM-123, ABC-456, etc.
        pattern = r'\b([A-Z]+-\d+)\b'
        matches = re.findall(pattern, message.upper())

        if matches:
            # Remove duplicates while preserving order
            seen = set()
            unique_matches = []
            for match in matches:
                if match not in seen:
                    seen.add(match)
                    unique_matches.append(match)
            return unique_matches

        # Check context for recent ticket mentions
        for msg in reversed(context):
            matches = re.findall(pattern, msg.get("content", "").upper())
            if matches:
                return matches[:1]  # Just first one from context

        return []

    def _extract_ticket_key(self, message: str, context: List[Dict[str, str]]) -> Optional[str]:
        """
        Extract single ticket key (for backward compatibility).

        Args:
            message: User message
            context: Conversation history

        Returns:
            First ticket key or None
        """
        keys = self._extract_ticket_keys(message, context)
        return keys[0] if keys else None

    def _analyze_ticket(
        self,
        issue: Dict[str, Any],
        links: List[Dict[str, Any]],
        comments: List[Dict[str, Any]],
        worklogs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze ticket data and extract insights.

        Args:
            issue: Full issue object from Jira
            links: Issue links (dependencies)
            comments: Issue comments
            worklogs: Work logs (time tracking)

        Returns:
            Analysis dict with extracted insights
        """
        fields = issue.get("fields", {})

        # Basic fields
        status = fields.get("status", {})
        priority = fields.get("priority", {})
        assignee = fields.get("assignee")
        issuetype = fields.get("issuetype", {})
        created = fields.get("created", "")
        updated = fields.get("updated", "")

        # Dependencies
        blocked_by = [link for link in links if link.get("direction") == "inward" and "blocked" in link.get("type", "").lower()]
        blocks = [link for link in links if link.get("direction") == "outward" and "blocks" in link.get("type", "").lower()]

        # Time analysis
        days_since_created = self._days_since(created)
        days_since_updated = self._days_since(updated)

        # Activity
        comment_count = len(comments)
        recent_comments = [c for c in comments if self._days_since(c.get("created", "")) <= 7]

        # Work logs analysis
        total_time_spent = 0  # in seconds
        worklog_authors = set()
        last_worklog_date = None

        for worklog in worklogs:
            time_spent = worklog.get("timeSpentSeconds", 0)
            total_time_spent += time_spent

            author = worklog.get("author", {})
            if author:
                author_name = author.get("displayName", "Unknown")
                worklog_authors.add(author_name)

            created = worklog.get("created", "")
            if created:
                if not last_worklog_date or created > last_worklog_date:
                    last_worklog_date = created

        # Convert seconds to hours
        total_hours = total_time_spent / 3600 if total_time_spent > 0 else 0
        days_since_last_worklog = self._days_since(last_worklog_date) if last_worklog_date else None

        # Comment analysis
        comment_authors = set()
        for comment in comments:
            author = comment.get("author", {})
            if author:
                author_name = author.get("displayName", "Unknown")
                comment_authors.add(author_name)

        return {
            "status": status.get("name", "Unknown"),
            "priority": priority.get("name", "None") if priority else "None",
            "type": issuetype.get("name", "Unknown") if issuetype else "Unknown",
            "assignee": assignee.get("displayName", "Unassigned") if assignee else "Unassigned",
            "has_assignee": assignee is not None,
            "created_days_ago": days_since_created,
            "updated_days_ago": days_since_updated,
            "is_stale": days_since_updated > 7,
            "blocked_by_count": len(blocked_by),
            "blocks_count": len(blocks),
            "blocked_by_tickets": [link["issue"]["key"] for link in blocked_by],
            "blocks_tickets": [link["issue"]["key"] for link in blocks],
            "comment_count": comment_count,
            "recent_comment_count": len(recent_comments),
            "has_recent_activity": len(recent_comments) > 0,
            "description_length": len(fields.get("description", "") or ""),
            "has_description": bool(fields.get("description")),
            # Worklog data
            "time_spent_hours": round(total_hours, 1),
            "worklog_count": len(worklogs),
            "worklog_authors": list(worklog_authors),
            "worklog_author_count": len(worklog_authors),
            "days_since_last_worklog": days_since_last_worklog,
            # Comment authors
            "comment_authors": list(comment_authors),
            "comment_author_count": len(comment_authors),
        }

    def _calculate_health_score(self, analysis: Dict[str, Any]) -> int:
        """
        Calculate ticket health score (0-100) based on analysis.

        Higher score = healthier ticket

        Args:
            analysis: Analysis dict from _analyze_ticket()

        Returns:
            Health score (0-100)
        """
        score = 100

        # Status penalties
        if analysis["status"] == "Blocked":
            score -= 30
        elif analysis["status"] == "To Do" and analysis["created_days_ago"] > 30:
            score -= 20  # Old ticket never started

        # Priority vs activity
        if analysis["priority"] in ["Highest", "High"]:
            if analysis["updated_days_ago"] > 7:
                score -= 25  # High priority but inactive
            if not analysis["has_assignee"]:
                score -= 20  # High priority but unassigned

        # Assignee
        if not analysis["has_assignee"]:
            score -= 15

        # Dependencies (blocking is bad)
        score -= analysis["blocked_by_count"] * 15  # Each blocker reduces score
        if analysis["blocks_count"] > 3:
            score -= 10  # Blocking many tickets is risky

        # Staleness
        if analysis["is_stale"]:
            score -= 10
            if analysis["updated_days_ago"] > 30:
                score -= 10  # Very stale

        # Activity (good sign)
        if analysis["has_recent_activity"]:
            score += 5
        if analysis["comment_count"] > 5:
            score += 5  # Active discussion

        # Description quality
        if not analysis["has_description"] or analysis["description_length"] < 50:
            score -= 10  # Poor description

        # Clamp to 0-100
        return max(0, min(100, score))

    def _generate_recommendations(self, analysis: Dict[str, Any], health_score: int) -> List[str]:
        """
        Generate actionable recommendations based on analysis.

        Args:
            analysis: Analysis dict
            health_score: Calculated health score

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Critical issues first
        if analysis["status"] == "Blocked":
            if analysis["blocked_by_count"] > 0:
                tickets = ", ".join(analysis["blocked_by_tickets"])
                recommendations.append(f"CRITICAL: Ticket is blocked by {analysis['blocked_by_count']} ticket(s): {tickets}. Resolve blockers immediately.")
            else:
                recommendations.append("CRITICAL: Ticket status is Blocked but no blocking links found. Update status or add blocker links.")

        # High priority issues
        if analysis["priority"] in ["Highest", "High"]:
            if not analysis["has_assignee"]:
                recommendations.append(f"HIGH: {analysis['priority']} priority ticket has no assignee. Assign immediately.")
            if analysis["updated_days_ago"] > 7:
                recommendations.append(f"HIGH: {analysis['priority']} priority ticket inactive for {analysis['updated_days_ago']} days. Request status update.")

        # Assignment
        if not analysis["has_assignee"] and analysis["status"] not in ["Done", "Closed"]:
            recommendations.append("Assign a developer to this ticket.")

        # Staleness
        if analysis["is_stale"] and analysis["status"] not in ["Done", "Closed", "Blocked"]:
            recommendations.append(f"Ticket hasn't been updated in {analysis['updated_days_ago']} days. Add a status update or close if no longer relevant.")

        # Dependencies
        if analysis["blocks_count"] > 3:
            tickets = ", ".join(analysis["blocks_tickets"][:3])
            recommendations.append(f"This ticket blocks {analysis['blocks_count']} other tickets ({tickets}...). Prioritize resolution.")

        # Activity
        if analysis["comment_count"] == 0 and analysis["created_days_ago"] > 3:
            recommendations.append("No comments on this ticket. Add initial analysis or questions.")

        # Description quality
        if not analysis["has_description"] or analysis["description_length"] < 50:
            recommendations.append("Improve ticket description. Add acceptance criteria, reproduction steps, or technical details.")

        # Old tickets in To Do
        if analysis["status"] == "To Do" and analysis["created_days_ago"] > 30:
            recommendations.append(f"Ticket in backlog for {analysis['created_days_ago']} days. Consider closing if no longer relevant, or start work.")

        # General health
        if health_score < 50:
            recommendations.append(f"Overall health score is low ({health_score}/100). This ticket needs immediate attention.")
        elif health_score >= 80:
            recommendations.append(f"Ticket is in good health ({health_score}/100). Continue current approach.")

        return recommendations if recommendations else ["No specific recommendations. Ticket appears healthy."]

    def _build_comparative_message(
        self,
        analyses: List[Dict[str, Any]],
        failed: List[Dict[str, str]]
    ) -> str:
        """
        Build comparative message for multiple ticket analysis.

        Args:
            analyses: List of analysis dicts
            failed: List of failed ticket dicts

        Returns:
            Formatted comparative message
        """
        lines = []
        lines.append(f"=== MULTI-TICKET ANALYSIS ({len(analyses)} tickets) ===")
        lines.append("")

        # Individual ticket summaries
        for i, analysis_data in enumerate(analyses, 1):
            ticket_key = analysis_data["ticket_key"]
            summary = analysis_data["summary"]
            health_score = analysis_data["health_score"]
            analysis = analysis_data["analysis"]
            recommendations = analysis_data["recommendations"]

            # Health status
            if health_score >= 70:
                health_label = "[GOOD]"
            elif health_score >= 40:
                health_label = "[WARNING]"
            else:
                health_label = "[CRITICAL]"

            # Risk level (simplified calculation)
            risk_score = 0
            if analysis['priority'] in ['Highest', 'High']:
                risk_score += 30
            if analysis['blocked_by_count'] > 0:
                risk_score += 25
            if analysis['is_stale']:
                risk_score += 20

            if risk_score >= 60:
                risk_label = "CRITICAL [!!!]"
            elif risk_score >= 40:
                risk_label = "HIGH [!!]"
            elif risk_score >= 20:
                risk_label = "MEDIUM [!]"
            else:
                risk_label = "LOW [OK]"

            lines.append(f"[{i}/{len(analyses)}] {ticket_key}")
            jira_url = f"{self.jira.base_url}/browse/{ticket_key}"
            lines.append(f"  Link: {jira_url}")
            lines.append(f"  Summary: {summary[:60]}{'...' if len(summary) > 60 else ''}")
            lines.append(f"  Health: {health_score}/100 {health_label}")
            lines.append(f"  Risk: {risk_label}")
            lines.append(f"  Status: {analysis['status']}, {analysis['priority']} priority")

            # Top issues
            issues = []
            if analysis['blocked_by_count'] > 0:
                issues.append(f"Blocked by {analysis['blocked_by_count']} ticket(s)")
            if analysis['is_stale']:
                issues.append(f"Inactive {analysis['updated_days_ago']} days")
            if not analysis['has_assignee']:
                issues.append("No assignee")
            if analysis['time_spent_hours'] == 0 and analysis['created_days_ago'] > 7:
                issues.append("No time logged")

            if issues:
                lines.append(f"  Issues: {', '.join(issues[:2])}")
            lines.append("")

        # Failed tickets
        if failed:
            lines.append("FAILED TO ANALYZE:")
            for fail in failed:
                lines.append(f"  - {fail['ticket_key']}: {fail['error']}")
            lines.append("")

        # Summary statistics
        lines.append("SUMMARY:")
        avg_health = sum(a["health_score"] for a in analyses) / len(analyses) if analyses else 0
        lines.append(f"  Total Analyzed: {len(analyses)}")
        lines.append(f"  Average Health: {avg_health:.0f}/100")

        # Find highest risk
        highest_risk = None
        highest_risk_score = 0
        for analysis_data in analyses:
            analysis = analysis_data["analysis"]
            risk_score = 0
            if analysis['priority'] in ['Highest', 'High']:
                risk_score += 30
            if analysis['blocked_by_count'] > 0:
                risk_score += 25
            if analysis['is_stale']:
                risk_score += 20
            if risk_score > highest_risk_score:
                highest_risk_score = risk_score
                highest_risk = analysis_data["ticket_key"]

        if highest_risk:
            lines.append(f"  Highest Risk: {highest_risk}")

        # Count tickets needing attention
        needs_attention = sum(1 for a in analyses if a["health_score"] < 60)
        if needs_attention > 0:
            lines.append(f"  Needs Immediate Attention: {needs_attention} ticket(s)")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)

    def _build_detailed_message(
        self,
        ticket_key: str,
        summary: str,
        health_score: int,
        analysis: Dict[str, Any],
        recommendations: List[str]
    ) -> str:
        """
        Build detailed analysis message for display.

        Args:
            ticket_key: Ticket key
            summary: Ticket summary
            health_score: Health score (0-100)
            analysis: Analysis dict
            recommendations: List of recommendations

        Returns:
            Formatted detailed message
        """
        # Health status emoji/indicator
        if health_score >= 80:
            health_status = "EXCELLENT"
            health_emoji = "[OK]"
        elif health_score >= 60:
            health_status = "GOOD"
            health_emoji = "[OK]"
        elif health_score >= 40:
            health_status = "NEEDS ATTENTION"
            health_emoji = "[WARNING]"
        else:
            health_status = "CRITICAL"
            health_emoji = "[ALERT]"

        # Build message sections
        lines = []
        lines.append(f"=== ANALYSIS: {ticket_key} ===")

        # Add clickable Jira link
        jira_url = f"{self.jira.base_url}/browse/{ticket_key}"
        lines.append(f"Link: {jira_url}")
        lines.append(f"Summary: {summary[:80]}{'...' if len(summary) > 80 else ''}")
        lines.append("")

        # Health Score
        lines.append(f"HEALTH SCORE: {health_score}/100 {health_emoji} {health_status}")
        lines.append("")

        # Ticket Details
        lines.append("TICKET DETAILS:")
        lines.append(f"  Status: {analysis['status']}")
        lines.append(f"  Priority: {analysis['priority']}")
        lines.append(f"  Type: {analysis['type']}")
        lines.append(f"  Assignee: {analysis['assignee']}")
        lines.append("")

        # Timeline
        lines.append("TIMELINE:")
        lines.append(f"  Created: {analysis['created_days_ago']} days ago")
        lines.append(f"  Last Updated: {analysis['updated_days_ago']} days ago")
        if analysis['is_stale']:
            lines.append(f"  Status: STALE (no activity in {analysis['updated_days_ago']} days)")
        else:
            lines.append(f"  Status: ACTIVE")
        lines.append("")

        # Dependencies
        lines.append("DEPENDENCIES:")
        if analysis['blocked_by_count'] > 0:
            blocked_by_str = ", ".join(analysis['blocked_by_tickets'])
            lines.append(f"  Blocked by: {analysis['blocked_by_count']} ticket(s) - {blocked_by_str}")
        else:
            lines.append(f"  Blocked by: None")

        if analysis['blocks_count'] > 0:
            blocks_str = ", ".join(analysis['blocks_tickets'])
            lines.append(f"  Blocks: {analysis['blocks_count']} ticket(s) - {blocks_str}")
        else:
            lines.append(f"  Blocks: None")
        lines.append("")

        # Time Tracking
        lines.append("TIME TRACKING:")
        if analysis['time_spent_hours'] > 0:
            lines.append(f"  Time Spent: {analysis['time_spent_hours']} hours")
            lines.append(f"  Work Logs: {analysis['worklog_count']} entries")
            lines.append(f"  Contributors: {analysis['worklog_author_count']} person(s)")
            if analysis['worklog_author_count'] > 0:
                authors = ", ".join(analysis['worklog_authors'][:3])
                if len(analysis['worklog_authors']) > 3:
                    authors += f" (+{len(analysis['worklog_authors']) - 3} more)"
                lines.append(f"    - {authors}")
            if analysis['days_since_last_worklog'] is not None:
                lines.append(f"  Last Work Log: {analysis['days_since_last_worklog']} days ago")
        else:
            lines.append(f"  Time Spent: No time logged")
        lines.append("")

        # Activity & Collaboration
        lines.append("ACTIVITY & COLLABORATION:")
        lines.append(f"  Total Comments: {analysis['comment_count']}")
        lines.append(f"  Recent Comments (7 days): {analysis['recent_comment_count']}")
        if analysis['comment_author_count'] > 0:
            lines.append(f"  Comment Authors: {analysis['comment_author_count']} person(s)")
            authors = ", ".join(analysis['comment_authors'][:3])
            if len(analysis['comment_authors']) > 3:
                authors += f" (+{len(analysis['comment_authors']) - 3} more)"
            lines.append(f"    - {authors}")
        if analysis['has_recent_activity']:
            lines.append(f"  Activity Level: HIGH (active discussion)")
        else:
            lines.append(f"  Activity Level: LOW (no recent activity)")
        lines.append("")

        # Description Quality
        lines.append("DESCRIPTION:")
        if analysis['has_description']:
            if analysis['description_length'] >= 100:
                lines.append(f"  Quality: GOOD ({analysis['description_length']} chars)")
            elif analysis['description_length'] >= 50:
                lines.append(f"  Quality: ACCEPTABLE ({analysis['description_length']} chars)")
            else:
                lines.append(f"  Quality: POOR ({analysis['description_length']} chars - too short)")
        else:
            lines.append(f"  Quality: MISSING (no description)")
        lines.append("")

        # Risk Assessment
        lines.append("RISK ASSESSMENT:")
        risk_factors = []
        risk_score = 0

        if analysis['priority'] in ['Highest', 'High']:
            risk_factors.append("High/Highest priority")
            risk_score += 30

        if analysis['blocked_by_count'] > 0:
            risk_factors.append(f"Blocked by {analysis['blocked_by_count']} ticket(s)")
            risk_score += 25

        if analysis['is_stale'] and analysis['status'] != 'Done':
            risk_factors.append(f"Inactive for {analysis['updated_days_ago']} days")
            risk_score += 20

        if not analysis['has_assignee']:
            risk_factors.append("No assignee")
            risk_score += 15

        if analysis['blocks_count'] > 3:
            risk_factors.append(f"Blocks {analysis['blocks_count']} other tickets")
            risk_score += 15

        if analysis['time_spent_hours'] == 0 and analysis['created_days_ago'] > 7:
            risk_factors.append("No time logged (ticket > 7 days old)")
            risk_score += 10

        if risk_score >= 60:
            risk_level = "CRITICAL"
            risk_emoji = "[!!!]"
        elif risk_score >= 40:
            risk_level = "HIGH"
            risk_emoji = "[!!]"
        elif risk_score >= 20:
            risk_level = "MEDIUM"
            risk_emoji = "[!]"
        else:
            risk_level = "LOW"
            risk_emoji = "[OK]"

        lines.append(f"  Risk Level: {risk_level} {risk_emoji} (Score: {risk_score}/100)")
        if risk_factors:
            lines.append(f"  Risk Factors:")
            for factor in risk_factors:
                lines.append(f"    - {factor}")
        else:
            lines.append(f"  Risk Factors: None identified")
        lines.append("")

        # Recommendations
        lines.append("RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            # Indent multi-line recommendations
            lines.append(f"  {i}. {rec}")
        lines.append("")

        lines.append("=" * 50)

        return "\n".join(lines)

    def _days_since(self, iso_date: str) -> int:
        """
        Calculate days since a given ISO date.

        Args:
            iso_date: ISO 8601 date string (e.g., "2025-01-15T10:30:00.000+0000")

        Returns:
            Days since date (integer)
        """
        if not iso_date:
            return 0

        try:
            # Parse ISO date (Jira format)
            date = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - date
            return delta.days
        except Exception:
            return 0
