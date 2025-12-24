"""
Example: Wagent APIを使用した簡単なエージェント
"""

from wagent.client import WagentClient
import time


def simple_research_agent():
    """
    シンプルな調査エージェント
    複数の質問を順番にChatGPTに投げて結果をまとめる
    """
    client = WagentClient()

    # サーバーの起動を待つ
    print("Waiting for Wagent server...")
    if not client.wait_for_server():
        print("Server is not available!")
        return

    # トピックリスト
    topics = [
        "Pythonの非同期処理について3行で説明して",
        "FastAPIの主な特徴を3つ挙げて",
        "Playwrightとは何か1文で説明して",
    ]

    results = []

    # 新しい会話を開始
    client.reset_session()

    for topic in topics:
        print(f"\n📝 Question: {topic}")

        response = client.chat(topic)

        if response["success"]:
            answer = response["message"]
            print(f"💬 Answer: {answer[:200]}...")
            results.append({"question": topic, "answer": answer})
        else:
            print(f"❌ Error: {response.get('error')}")

        # レートリミット対策
        time.sleep(3)

    # 結果をまとめ
    print("\n" + "=" * 50)
    print("📊 Research Summary")
    print("=" * 50)

    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['question']}")
        print(f"   → {result['answer'][:100]}...")


def code_review_agent():
    """
    コードレビューエージェント
    コードを投げてレビューコメントをもらう
    """
    client = WagentClient()

    if not client.wait_for_server():
        return

    code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
    """

    prompt = f"""
以下のPythonコードをレビューしてください。
問題点と改善案を簡潔に述べてください。

```python
{code}
```
"""

    # 新しい会話で質問
    response = client.chat(prompt, new_conversation=True)

    if response["success"]:
        print("🔍 Code Review Result:")
        print(response["message"])
    else:
        print(f"Error: {response.get('error')}")


if __name__ == "__main__":
    print("Select example:")
    print("1. Simple Research Agent")
    print("2. Code Review Agent")

    choice = input("Enter number: ").strip()

    if choice == "1":
        simple_research_agent()
    elif choice == "2":
        code_review_agent()
    else:
        print("Invalid choice")
