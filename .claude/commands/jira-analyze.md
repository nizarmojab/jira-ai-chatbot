# /jira-analyze

Deep analysis of a Jira ticket using LLM.

## Usage
```
/jira-analyze <TICKET-KEY>
```

## Examples
```
/jira-analyze SCRUM-5
/jira-analyze SCRUM-214
```

## Instructions for Claude Code

When this command is invoked:
1. Fetch full ticket via `get_issue(key)`
2. Fetch dependencies via `get_dependencies(key)`
3. Fetch comments via `get_comments(key)`
4. Use GPT-4o to analyze:
   - Summary of the issue in plain language
   - Root cause identification
   - Impact assessment (what does it block?)
   - Health score (0-100) based on: description completeness, AC present, assignee, priority, overdue status
   - Recommended next actions
5. Display as Rich panel with sections

## Health Score Criteria

| Criterion | Points |
|---|---|
| Description has Steps to Reproduce | +15 |
| Description has Acceptance Criteria | +15 |
| Assignee is set | +10 |
| Priority is set (not None) | +10 |
| Story points set (for Story/Task) | +10 |
| Not overdue | +20 |
| No blocker dependencies unresolved | +20 |

Score ranges:
- 80-100: 🟢 Healthy
- 50-79:  🟡 Needs attention
- 0-49:   🔴 Critical issues