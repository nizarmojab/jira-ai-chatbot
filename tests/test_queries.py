"""
test_queries.py
===============
20 NLP test queries to validate the chatbot.
Run manually by pasting each query into the chatbot CLI.
"""

TEST_QUERIES = [
    # ── Search queries ─────────────────────────────────
    {
        "id": "T01",
        "query": "show me critical bugs",
        "expected_jql": "project = SCRUM AND issuetype = Bug AND priority = Highest",
        "expected_count": "~9 results",
    },
    {
        "id": "T02",
        "query": "quels tickets sont bloqués ?",
        "expected_jql": "project = SCRUM AND status = Blocked",
        "expected_count": "~27 results",
    },
    {
        "id": "T03",
        "query": "bugs in CAN component",
        "expected_jql": "project = SCRUM AND issuetype = Bug AND labels = canbus",
        "expected_count": "~12 results",
    },
    {
        "id": "T04",
        "query": "tickets assigned to Marelli",
        "expected_jql": "project = SCRUM AND labels = marelli",
        "expected_count": "~50 results",
    },
    {
        "id": "T05",
        "query": "what is overdue this sprint",
        "expected_jql": "project = SCRUM AND duedate < now() AND status != Done",
        "expected_count": "~49 results",
    },
    {
        "id": "T06",
        "query": "show tech debt backlog",
        "expected_jql": "project = SCRUM AND labels = tech-debt",
        "expected_count": "10 results",
    },
    {
        "id": "T07",
        "query": "regressions detected",
        "expected_jql": "project = SCRUM AND labels = regression",
        "expected_count": "3-6 results",
    },
    {
        "id": "T08",
        "query": "unassigned high priority bugs",
        "expected_jql": "project = SCRUM AND issuetype = Bug AND priority in (Highest, High) AND assignee is EMPTY",
        "expected_count": "varies",
    },

    # ── Analysis queries ───────────────────────────────
    {
        "id": "T09",
        "query": "analyze SCRUM-5",
        "expected": "Full analysis panel: summary, root cause, health score, recommendations",
    },
    {
        "id": "T10",
        "query": "what is blocking the sprint ?",
        "expected": "List of blockers with dependency chain",
    },
    {
        "id": "T11",
        "query": "find root cause of blockers",
        "expected": "SCRUM-5 identified as root cause blocking 5 stories",
    },
    {
        "id": "T12",
        "query": "which tickets are duplicates ?",
        "expected": "LLM similarity analysis of similar tickets",
    },

    # ── Action queries ─────────────────────────────────
    {
        "id": "T13",
        "query": "improve description of SCRUM-42",
        "expected": "GPT-4o generates enriched description with AC, steps, environment",
    },
    {
        "id": "T14",
        "query": "change priority of SCRUM-5 to High",
        "expected": "Confirmation prompt then PUT /issue/SCRUM-5",
    },
    {
        "id": "T15",
        "query": "notify Marelli on SCRUM-7",
        "expected": "@mention comment posted on SCRUM-7",
    },

    # ── Report queries ─────────────────────────────────
    {
        "id": "T16",
        "query": "sprint report",
        "expected": "Full Sprint 4 health report with velocity, risks, recommendations",
    },
    {
        "id": "T17",
        "query": "prepare standup",
        "expected": "Done yesterday / Today / Blockers — ready to read",
    },
    {
        "id": "T18",
        "query": "what should I prioritize ?",
        "expected": "Top 3 action recommendations based on current project state",
    },
    {
        "id": "T19",
        "query": "compare sprint 3 and sprint 4",
        "expected": "Velocity diff, bug trends, component breakdown",
    },

    # ── Open in Jira ───────────────────────────────────
    {
        "id": "T20",
        "query": "open SCRUM-5",
        "expected": "Browser opens https://chatbotjira.atlassian.net/browse/SCRUM-5",
    },
]

if __name__ == "__main__":
    print(f"Total test queries: {len(TEST_QUERIES)}")
    print("\nRun these manually in the chatbot CLI:")
    for t in TEST_QUERIES:
        print(f"\n[{t['id']}] {t['query']}")
        if 'expected_jql' in t:
            print(f"     Expected JQL: {t['expected_jql']}")
        if 'expected' in t:
            print(f"     Expected: {t['expected']}")