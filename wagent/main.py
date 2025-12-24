"""
Wagent - メインエントリーポイント
サーバーの起動と対話モードの両方をサポート
"""

import asyncio
import argparse
import sys
from pathlib import Path

import uvicorn
from loguru import logger

# logsディレクトリを作成
(Path(__file__).parent.parent / "logs").mkdir(exist_ok=True)
(Path(__file__).parent.parent / "screenshots").mkdir(exist_ok=True)

# ロギング設定
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add("logs/wagent.log", rotation="10 MB", level="DEBUG")


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """APIサーバーを起動"""
    logger.info(f"Starting Wagent API server on {host}:{port}")
    uvicorn.run(
        "wagent.server:app", host=host, port=port, reload=False, log_level="info"
    )


async def interactive_mode():
    """対話モード - デバッグ・テスト用"""
    from .browser import browser

    logger.info("Starting interactive mode...")

    await browser.initialize()
    await browser.navigate_to_chatgpt()

    # ログイン状態確認
    logged_in = await browser.is_logged_in()
    if not logged_in:
        logger.warning("Not logged in! Please log in manually in the browser window.")
        logger.info("Press Enter when you've logged in...")
        input()

    logger.info("Ready! Enter your prompts (type 'quit' to exit):")

    while True:
        try:
            prompt = input("\n[You] > ").strip()

            if prompt.lower() in ("quit", "exit", "q"):
                break

            if not prompt:
                continue

            if prompt == "/new":
                await browser.new_chat()
                logger.info("Started new chat")
                continue

            if prompt == "/screenshot":
                path = await browser.screenshot()
                logger.info(f"Screenshot saved: {path}")
                continue

            # プロンプト送信
            await browser.send_prompt(prompt)

            # レスポンス取得
            response = await browser.wait_for_response()
            print(f"\n[ChatGPT] > {response}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error: {e}")

    await browser.close()
    logger.info("Goodbye!")


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="Wagent - ChatGPT Web UI Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # APIサーバーを起動
  python -m wagent.main --server
  
  # 対話モードで起動
  python -m wagent.main --interactive
  
  # カスタムポートで起動
  python -m wagent.main --server --port 9000
        """,
    )

    parser.add_argument(
        "-s", "--server", action="store_true", help="APIサーバーモードで起動"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="対話モードで起動（デバッグ用）",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="サーバーのホスト (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="サーバーのポート (default: 8765)"
    )

    args = parser.parse_args()

    if args.server:
        run_server(args.host, args.port)
    elif args.interactive:
        asyncio.run(interactive_mode())
    else:
        parser.print_help()
        print("\nPlease specify --server or --interactive mode")


if __name__ == "__main__":
    main()
