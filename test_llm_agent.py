#!/usr/bin/env python3
"""Test LLM agent with tool execution"""
import sys
sys.path.insert(0, '.')

from src.llm_agent import JiraAgent

print("Testing LLM Agent...")
print("="*50)

agent = JiraAgent()
print(f"Agent initialized with model: {agent.model}\n")

query = "donne moi les bugs critiques"
print(f"Query: {query}")
print("-"*50)

try:
    result = agent.process_query(query)

    print("\nResult:")
    print(f"  Response: {result['response'][:200]}...")
    print(f"  Tickets: {len(result.get('tickets', []))}")
    print(f"  JQL: {result.get('jql')}")
    print(f"  Metadata: {result.get('metadata')}")

    if result.get('tickets'):
        print("\nFirst ticket:")
        print(f"  {result['tickets'][0]['key']}: {result['tickets'][0]['summary']}")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
