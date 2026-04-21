#!/usr/bin/env python3
"""Minimal test to debug GPT-4o tool calls"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Simple tool definition
tools = [{
    "type": "function",
    "function": {
        "name": "test_tool",
        "description": "A simple test tool",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            },
            "required": ["message"]
        }
    }
}]

print("Testing GPT-4o with tools...")
print("="*50)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Use the test_tool when the user asks for a test."},
        {"role": "user", "content": "call the test tool with message 'hello'"}
    ],
    tools=tools,
    tool_choice="auto"
)

message = response.choices[0].message
print(f"Finish reason: {response.choices[0].finish_reason}")
print(f"Has tool_calls: {hasattr(message, 'tool_calls')}")
print(f"Message content: {message.content}")

if hasattr(message, 'tool_calls') and message.tool_calls:
    print(f"\nTool calls: {len(message.tool_calls)}")
    for tc in message.tool_calls:
        print(f"  - {tc.function.name}({tc.function.arguments})")
else:
    print("\nNo tool calls!")
