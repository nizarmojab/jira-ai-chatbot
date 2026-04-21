# /jira-update

Update Jira tickets via conversation.

## Usage
```
/jira-update <TICKET-KEY> <what to update>
```

## Examples
```
/jira-update SCRUM-5 priority High
/jira-update SCRUM-42 improve description
/jira-update SCRUM-7 add comment "Fix deployed on bench"
/jira-update SCRUM-5 status "In Progress"
```

## Instructions for Claude Code

### ALWAYS ask for confirmation before writing to Jira
Show a preview of the change and ask "Confirm? (yes/no)" before executing.

### Allowed updates
| Action | API call |
|---|---|
| Change priority | `PUT /issue/{key}` → `fields.priority` |
| Change status | `POST /issue/{key}/transitions` |
| Change assignee | `PUT /issue/{key}` → `fields.assignee` |
| Add comment | `POST /issue/{key}/comment` |
| Improve description | `PUT /issue/{key}` → `fields.description` (ADF) |
| Change labels | `PUT /issue/{key}` → `fields.labels` |
| Change story points | `PUT /issue/{key}` → `fields.customfield_10016` |

### Description improvement
When asked to improve a description:
1. Fetch current description
2. Use GPT-4o to generate enriched version with:
   - Environment section
   - Steps to Reproduce
   - Actual behavior
   - Expected behavior
   - Acceptance Criteria
3. Show diff (before/after)
4. Ask for confirmation
5. Apply via PUT /issue/{key}

### Safety rules
- Never delete tickets
- Never change Epic assignments without explicit confirmation
- Always log what was changed: "Updated SCRUM-5: priority Medium → High"