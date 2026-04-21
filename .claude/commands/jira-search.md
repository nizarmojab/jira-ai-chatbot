# /jira-search

Search Jira tickets using natural language.

## Usage
```
/jira-search <natural language query>
```

## Examples
```
/jira-search critical bugs in CAN component
/jira-search tickets bloqués chez Marelli
/jira-search overdue stories in sprint 4
/jira-search unassigned high priority bugs
```

## Instructions for Claude Code

When this command is invoked:
1. Extract the search intent from the query
2. Call `src/jira_tools.py → search_issues()` with appropriate JQL
3. Display results as a Rich table with columns: Key, Type, Summary, Status, Priority
4. Show total count and the JQL used
5. Each ticket key must be a clickable URL: `https://chatbotjira.atlassian.net/browse/{KEY}`

## JQL mapping

| Natural language | JQL clause |
|---|---|
| "critical" / "highest" | `priority = Highest` |
| "blocked" | `status = Blocked` |
| "in progress" | `status = "In Progress"` |
| "overdue" | `duedate < now() AND status != Done` |
| "my tickets" | `assignee = currentUser()` |
| "unassigned" | `assignee is EMPTY` |
| "bugs" | `issuetype = Bug` |
| "stories" | `issuetype = Story` |
| "CAN" / "canbus" | `labels = canbus` |
| "Marelli" | `labels = marelli` |
| "Harman" | `labels = harman` |
| "regression" | `labels = regression` |
| "tech debt" | `labels = tech-debt` |