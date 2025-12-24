#!/usr/bin/env python
"""
Wagent Agent Examples
=====================

Wagent APIを使用した様々なエージェントパターンの実装例。

Usage:
    $ rye run python examples/simple_agent.py
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from wagent.client import WagentClient

# =============================================================================
# 基底エージェントクラス
# =============================================================================


class BaseAgent(ABC):
    """エージェントの基底クラス"""

    def __init__(
        self,
        client: Optional[WagentClient] = None,
        verbose: bool = True,
    ) -> None:
        self.client = client or WagentClient()
        self.verbose = verbose

    def log(self, message: str) -> None:
        """ログ出力"""
        if self.verbose:
            print(message)

    @abstractmethod
    def run(self) -> None:
        """エージェントを実行"""
        ...


# =============================================================================
# リサーチエージェント
# =============================================================================


@dataclass
class ResearchResult:
    """リサーチ結果"""

    question: str
    answer: Optional[str]
    success: bool
    elapsed_seconds: float


class ResearchAgent(BaseAgent):
    """
    リサーチエージェント

    複数の質問を順番にChatGPTに投げて結果をまとめる。
    """

    def __init__(
        self,
        questions: list[str],
        delay_between: float = 3.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.questions = questions
        self.delay_between = delay_between
        self.results: list[ResearchResult] = []

    def run(self) -> None:
        """リサーチを実行"""
        self.log("🔬 Starting Research Agent...")
        self.log(f"   Questions: {len(self.questions)}")
        self.log("")

        # サーバー接続確認
        if not self.client.wait_for_server(max_retries=10):
            self.log("❌ Server not available")
            return

        # 新しい会話を開始
        self.client.reset_session()

        for i, question in enumerate(self.questions, 1):
            self.log(f"📝 [{i}/{len(self.questions)}] {question[:50]}...")

            result = self.client.chat(question)

            research_result = ResearchResult(
                question=question,
                answer=result.message if result.success else None,
                success=result.success,
                elapsed_seconds=result.elapsed_seconds,
            )
            self.results.append(research_result)

            if result.success:
                self.log(f"   ✅ Got response ({result.response_length} chars)")
            else:
                self.log(f"   ❌ Error: {result.error}")

            # レートリミット対策
            if i < len(self.questions):
                time.sleep(self.delay_between)

        self._print_summary()

    def _print_summary(self) -> None:
        """サマリーを表示"""
        self.log("")
        self.log("=" * 60)
        self.log("📊 Research Summary")
        self.log("=" * 60)

        success_count = sum(1 for r in self.results if r.success)
        total_time = sum(r.elapsed_seconds for r in self.results)

        self.log(f"   Success: {success_count}/{len(self.results)}")
        self.log(f"   Total Time: {total_time:.1f}s")
        self.log("")

        for i, result in enumerate(self.results, 1):
            status = "✅" if result.success else "❌"
            preview = (
                result.answer[:80] + "..."
                if result.answer and len(result.answer) > 80
                else result.answer or "N/A"
            )
            self.log(f"{status} Q{i}: {result.question[:40]}...")
            self.log(f"    → {preview}")
            self.log("")


# =============================================================================
# コードレビューエージェント
# =============================================================================


@dataclass
class ReviewResult:
    """レビュー結果"""

    code: str
    review: Optional[str]
    issues_found: int = 0
    suggestions: list[str] = field(default_factory=list)


class CodeReviewAgent(BaseAgent):
    """
    コードレビューエージェント

    コードを投げてレビューコメントをもらう。
    """

    REVIEW_PROMPT_TEMPLATE = """
以下のコードをレビューしてください。

レビュー観点:
1. バグや潜在的な問題点
2. パフォーマンス改善の余地
3. 可読性・保守性
4. ベストプラクティスへの準拠

コード:
```{language}
{code}
```

問題点と改善案を箇条書きで簡潔に述べてください。
"""

    def __init__(
        self,
        code: str,
        language: str = "python",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.code = code
        self.language = language
        self.result: Optional[ReviewResult] = None

    def run(self) -> None:
        """レビューを実行"""
        self.log("🔍 Starting Code Review Agent...")
        self.log("")

        if not self.client.wait_for_server(max_retries=10):
            self.log("❌ Server not available")
            return

        prompt = self.REVIEW_PROMPT_TEMPLATE.format(
            language=self.language,
            code=self.code,
        )

        result = self.client.chat(prompt, new_conversation=True)

        if result.success:
            self.result = ReviewResult(
                code=self.code,
                review=result.message,
            )
            self.log("✅ Review completed!")
            self.log("")
            self.log("=" * 60)
            self.log("📝 Code Review Result")
            self.log("=" * 60)
            self.log(result.message)
        else:
            self.log(f"❌ Error: {result.error}")


# =============================================================================
# 翻訳エージェント
# =============================================================================


class TranslationAgent(BaseAgent):
    """
    翻訳エージェント

    テキストを指定言語に翻訳する。
    """

    TRANSLATE_PROMPT = """
以下のテキストを{target_lang}に翻訳してください。
翻訳のみを出力し、説明は不要です。

テキスト:
{text}
"""

    def __init__(
        self,
        text: str,
        target_lang: str = "English",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.text = text
        self.target_lang = target_lang
        self.translation: Optional[str] = None

    def run(self) -> None:
        """翻訳を実行"""
        self.log(f"🌐 Translating to {self.target_lang}...")

        if not self.client.wait_for_server(max_retries=10):
            self.log("❌ Server not available")
            return

        prompt = self.TRANSLATE_PROMPT.format(
            target_lang=self.target_lang,
            text=self.text,
        )

        result = self.client.chat(prompt, new_conversation=True)

        if result.success:
            self.translation = result.message
            self.log("\n✅ Translation:")
            self.log("-" * 40)
            self.log(self.translation)
        else:
            self.log(f"❌ Error: {result.error}")


# =============================================================================
# メイン
# =============================================================================


def demo_research_agent() -> None:
    """リサーチエージェントのデモ"""
    questions = [
        "Pythonの非同期処理について3行で説明して",
        "FastAPIの主な特徴を3つ挙げて",
        "Playwrightとは何か1文で説明して",
    ]
    agent = ResearchAgent(questions=questions)
    agent.run()


def demo_code_review_agent() -> None:
    """コードレビューエージェントのデモ"""
    code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def sort_list(items):
    for i in range(len(items)):
        for j in range(len(items)):
            if items[i] < items[j]:
                items[i], items[j] = items[j], items[i]
    return items
"""
    agent = CodeReviewAgent(code=code, language="python")
    agent.run()


def demo_translation_agent() -> None:
    """翻訳エージェントのデモ"""
    text = """
    Wagentは、Web版ChatGPTをAPIとして利用するためのブリッジツールです。
    Playwrightによるブラウザ自動化を使用して、外部プログラムからChatGPTを操作できます。
    """
    agent = TranslationAgent(text=text, target_lang="English")
    agent.run()


def main() -> None:
    """メイン処理"""
    print("=" * 60)
    print("Wagent Agent Examples")
    print("=" * 60)
    print()
    print("Select an example to run:")
    print("  1. Research Agent")
    print("  2. Code Review Agent")
    print("  3. Translation Agent")
    print("  q. Quit")
    print()

    choice = input("Enter choice: ").strip().lower()

    if choice == "1":
        demo_research_agent()
    elif choice == "2":
        demo_code_review_agent()
    elif choice == "3":
        demo_translation_agent()
    elif choice == "q":
        print("Goodbye!")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
