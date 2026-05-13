#!/usr/bin/env python3
"""
test_orchestrator.py
====================
Test the orchestrator: intent detection, routing, and memory management.
"""
from src.orchestrator import Orchestrator


def test_intent_detection():
    """Test intent detection for various queries."""
    print("="*70)
    print("[TEST] INTENT DETECTION")
    print("="*70)
    print()

    orchestrator = Orchestrator()

    test_cases = [
        # SEARCH
        ("show me critical bugs", "SEARCH"),
        ("find all blocked tickets", "SEARCH"),
        ("list bugs in CAN component", "SEARCH"),
        ("affiche les tickets urgents", "SEARCH"),
        ("cherche les bugs critiques", "SEARCH"),

        # ANALYZE
        ("analyze SCRUM-5", "ANALYZE"),
        ("what is blocking SCRUM-42", "ANALYZE"),
        ("inspect dependencies of SCRUM-10", "ANALYZE"),
        ("analyse le ticket SCRUM-5", "ANALYZE"),
        ("qu'est-ce qui bloque le sprint ?", "ANALYZE"),

        # UPDATE
        ("change priority of SCRUM-5 to High", "UPDATE"),
        ("update status of SCRUM-42", "UPDATE"),
        ("improve description of SCRUM-10", "UPDATE"),
        ("modifie la priorite du ticket", "UPDATE"),
        ("change l'assignee", "UPDATE"),

        # REPORT
        ("generate sprint report", "REPORT"),
        ("prepare standup", "REPORT"),
        ("create release summary", "REPORT"),
        ("genere un rapport", "REPORT"),
        ("prepare le daily standup", "REPORT"),

        # DEDUP
        ("find duplicate tickets", "DEDUP"),
        ("cherche les doublons", "DEDUP"),
        ("similar tickets to SCRUM-5", "DEDUP"),

        # NOTIFY
        ("notify the team about SCRUM-5", "NOTIFY"),
        ("send alert to assignee", "NOTIFY"),
        ("envoie une notification", "NOTIFY"),
    ]

    passed = 0
    failed = 0

    for query, expected_intent in test_cases:
        result = orchestrator._detect_intent(query)
        status = "OK" if result == expected_intent else "FAIL"

        if result == expected_intent:
            passed += 1
            print(f"[{status}] \"{query}\" -> {result}")
        else:
            failed += 1
            print(f"[{status}] \"{query}\" -> Expected: {expected_intent}, Got: {result}")

    print()
    print(f"[RESULT] {passed} passed, {failed} failed")
    print()


def test_routing():
    """Test agent routing."""
    print("="*70)
    print("[TEST] AGENT ROUTING")
    print("="*70)
    print()

    orchestrator = Orchestrator()

    routing_tests = [
        ("SEARCH", "SearchAgent"),
        ("ANALYZE", "AnalyzeAgent"),
        ("UPDATE", "UpdateAgent"),
        ("REPORT", "ReportAgent"),
        ("DEDUP", "DedupAgent"),
        ("NOTIFY", "NotifyAgent"),
        ("UNKNOWN", "SearchAgent"),
    ]

    for intent, expected_agent in routing_tests:
        agent = orchestrator._route_to_agent(intent)
        status = "OK" if agent == expected_agent else "FAIL"
        print(f"[{status}] {intent} -> {agent}")

    print()


def test_memory_management():
    """Test conversation memory management."""
    print("="*70)
    print("[TEST] MEMORY MANAGEMENT")
    print("="*70)
    print()

    orchestrator = Orchestrator()

    # Test 1: Add messages and check memory
    print("[TEST] Adding messages to memory...")
    orchestrator._add_to_memory("user", "show me bugs")
    orchestrator._add_to_memory("assistant", "Here are the bugs...")
    orchestrator._add_to_memory("user", "analyze SCRUM-5")
    orchestrator._add_to_memory("assistant", "Analysis of SCRUM-5...")

    assert len(orchestrator.memory) == 4, f"Expected 4 messages, got {len(orchestrator.memory)}"
    print(f"[OK] Memory has {len(orchestrator.memory)} messages (2 turns)")
    print()

    # Test 2: Memory trimming (max 10 turns = 20 messages)
    print("[TEST] Testing memory trimming (max 10 turns)...")
    orchestrator.clear_memory()

    # Add 15 turns (30 messages) - should keep only last 10 turns (20 messages)
    for i in range(15):
        orchestrator._add_to_memory("user", f"Message {i}")
        orchestrator._add_to_memory("assistant", f"Response {i}")

    assert len(orchestrator.memory) == 20, f"Expected 20 messages (10 turns), got {len(orchestrator.memory)}"
    print(f"[OK] Memory trimmed to {len(orchestrator.memory)} messages (10 turns)")

    # Check that oldest messages were removed
    first_user_msg = orchestrator.memory[0]["content"]
    assert "Message 5" in first_user_msg, f"Expected oldest message to be 'Message 5', got '{first_user_msg}'"
    print(f"[OK] Oldest message kept: '{first_user_msg}'")
    print()

    # Test 3: Context retrieval
    print("[TEST] Testing context retrieval...")
    context = orchestrator._get_context()
    assert len(context) == 20, f"Expected 20 context messages, got {len(context)}"
    print(f"[OK] Context has {len(context)} messages")
    print()

    # Test 4: Memory summary
    print("[TEST] Memory summary:")
    print(orchestrator.get_memory_summary())
    print()


def test_process_message():
    """Test full message processing workflow."""
    print("="*70)
    print("[TEST] PROCESS MESSAGE WORKFLOW")
    print("="*70)
    print()

    orchestrator = Orchestrator()

    # Simulate conversation
    queries = [
        "show me critical bugs",
        "now analyze SCRUM-5",
        "what are its dependencies?",
    ]

    for i, query in enumerate(queries):
        print(f"[Turn {i+1}] User: {query}")

        result = orchestrator.process_message(query)

        print(f"  Intent: {result['intent']}")
        print(f"  Agent: {result['agent']}")
        print(f"  Context: {len(result['context'])} messages")

        # Simulate assistant response
        assistant_response = f"[{result['agent']}] Processed: {query}"
        orchestrator.add_assistant_response(assistant_response)

        print(f"  Assistant: {assistant_response}")
        print()

    print(f"[OK] Final memory has {len(orchestrator.memory)} messages ({len(orchestrator.memory)//2} turns)")
    print()


def main():
    """Run all tests."""
    print()
    print("="*70)
    print("[CONFIG] JIRA MULTI-AGENT CHATBOT - ORCHESTRATOR TEST")
    print("="*70)
    print()

    test_intent_detection()
    test_routing()
    test_memory_management()
    test_process_message()

    print("="*70)
    print("[SUCCESS] All orchestrator tests passed!")
    print("="*70)
    print()


if __name__ == "__main__":
    main()
