# /jira-report

Generate intelligent reports from Jira data.

## Usage
```
/jira-report sprint          → Sprint health report
/jira-report standup         → Daily standup content
/jira-report release         → Release readiness report
/jira-report blockers        → Blocker analysis with root cause
```

## Instructions for Claude Code

### Sprint report
1. Fetch active sprint via `get_sprint_info()`
2. Fetch all sprint tickets via `search_issues(jql="sprint in openSprints()")`
3. Analyze with GPT-4o:
   - Velocity vs target
   - Done / In Progress / Blocked / Not started counts
   - Risk assessment for release
   - Top 3 recommendations
4. Display as Rich panel with colored sections

### Standup report
1. Fetch tickets updated in last 24h: `updated >= -1d`
2. Fetch blocked tickets: `status = Blocked`
3. GPT-4o generates:
   - ✅ Done yesterday
   - 🔄 In progress today
   - 🚫 Blockers
4. Output ready to read in meeting (plain text format)

### Blocker analysis
1. Fetch all blocked tickets
2. For each: traverse dependency chain upward
3. Identify root cause ticket(s)
4. GPT-4o generates:
   - Critical path visualization (text tree)
   - Root cause identification
   - Impact count (how many tickets blocked)
   - Recommended resolution order