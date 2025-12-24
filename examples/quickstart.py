#!/usr/bin/env python
"""
Wagent Quick Start Example
==========================

Wagent APIの基本的な使い方を示すサンプルコード。

Usage:
    1. Start the Wagent server first:
       $ rye run wagent --server

    2. Run this example:
       $ rye run python examples/quickstart.py
"""

from wagent.client import WagentClient


def main() -> None:
    """メイン処理"""
    # クライアントを作成
    client = WagentClient()

    print("=" * 60)
    print("Wagent Quick Start Example")
    print("=" * 60)

    # サーバー接続を待機
    print("\n🔌 Connecting to Wagent server...")
    if not client.wait_for_server(max_retries=10):
        print("❌ Error: Could not connect to Wagent server.")
        print("   Make sure the server is running:")
        print("   $ rye run wagent --server")
        return

    # ステータスを確認
    print("\n📊 Checking status...")
    status = client.status()
    print(f"   Browser Status: {status.browser_status}")
    print(f"   Logged In: {status.logged_in}")
    print(f"   Headless Mode: {status.headless}")

    if not status.logged_in:
        print("\n⚠️  Warning: Not logged in to ChatGPT.")
        print("   Please login first using:")
        print("   $ rye run wagent --interactive")
        return

    # メッセージを送信
    print("\n💬 Sending test message...")
    result = client.chat(
        message="Please respond with 'Wagent is working!' to confirm the connection.",
        new_conversation=True,
    )

    if result.success:
        print("\n✅ Response received!")
        print("-" * 40)
        print(result.message)
        print("-" * 40)
        print("\n📈 Statistics:")
        print(f"   Elapsed: {result.elapsed_seconds:.2f}s")
        print(f"   Prompt Length: {result.prompt_length} chars")
        print(f"   Response Length: {result.response_length} chars")
    else:
        print(f"\n❌ Error: {result.error}")


if __name__ == "__main__":
    main()
