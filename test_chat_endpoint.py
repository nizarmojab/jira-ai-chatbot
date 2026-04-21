#!/usr/bin/env python3
"""Test the /chat endpoint directly"""
import requests
import json

url = "http://localhost:5001/chat"
payload = {"message": "montre-moi les bugs critiques"}

print("Testing /chat endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
