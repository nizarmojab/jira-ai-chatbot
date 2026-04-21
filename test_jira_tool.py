#!/usr/bin/env python3
"""Test Jira tools directly"""
import sys
sys.path.insert(0, '.')

from src.jira_tools import search_issues

print("Testing search_issues tool...")
print("="*50)

# Test search for critical bugs
jql = "project = SCRUM AND issuetype = Bug AND priority = Highest"
print(f"JQL: {jql}\n")

result = search_issues(jql, max_results=5)

print("Result:")
print(f"  Success: {result.get('success')}")
print(f"  Total: {result.get('total')}")
print(f"  Issues returned: {len(result.get('issues', []))}")

if result.get('error'):
    print(f"  ERROR: {result['error']}")

if result.get('issues'):
    print("\nFirst issue:")
    print(f"  {result['issues'][0]}")
