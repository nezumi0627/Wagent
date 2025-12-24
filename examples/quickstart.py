#!/usr/bin/env python
"""
Wagent Quick Start Example
==========================

This is a simple example of using Wagent to interact with ChatGPT.

Usage:
    1. Start the Wagent server first:
       $ rye run wagent --server

    2. Run this example:
       $ rye run python examples/quickstart.py
"""

from wagent.client import WagentClient


def main():
    # Create a client
    client = WagentClient()

    # Wait for server to be ready
    print("Connecting to Wagent server...")
    if not client.wait_for_server(max_retries=10):
        print("Error: Could not connect to Wagent server.")
        print("Make sure the server is running: rye run wagent --server")
        return

    # Check status
    status = client.status()
    print(f"Server status: {status['status']}")
    print(f"Logged in: {status['logged_in']}")

    if not status["logged_in"]:
        print("\nWarning: Not logged in to ChatGPT.")
        print("Please login first using: rye run wagent --interactive")
        return

    # Send a message
    print("\nSending message to ChatGPT...")
    response = client.chat(
        "Hello! Please respond with 'Wagent is working!' to confirm."
    )

    if response["success"]:
        print("\n✅ Response received:")
        print(response["message"])
    else:
        print(f"\n❌ Error: {response.get('error')}")


if __name__ == "__main__":
    main()
