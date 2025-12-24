"""
Main - Wagentエントリーポイント

サーバーモードと対話モードの両方をサポート。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from loguru import logger

if TYPE_CHECKING:
    from wagent.browser import BrowserController

# =============================================================================
# ロギング設定
# =============================================================================


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """ロギングを設定"""
    # デフォルトハンドラーを削除
    logger.remove()

    # コンソール出力
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> - <level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )

    # ファイル出力
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            rotation="10 MB",
            retention=5,
            level="DEBUG",
        )


# =============================================================================
# 対話モード
# =============================================================================


async def run_interactive_mode() -> None:
    """対話モードで実行"""
    from wagent.browser import BrowserController
    from wagent.config import Config, Selectors

    config = Config.load()
    selectors = Selectors.load()

    setup_logging(config.logging.level, config.logging.file)

    logger.info("Starting interactive mode...")
    logger.info(f"Headless: {config.browser.headless}")

    async with BrowserController.create(config, selectors) as browser:
        await browser.navigate_to_chatgpt()

        # ログイン状態確認
        logged_in = await browser.is_logged_in()
        if not logged_in:
            logger.warning("Not logged in!")
            logger.info("Please log in manually in the browser window.")
            logger.info("Press Enter when you've logged in...")
            input()

        print_interactive_help()

        while True:
            try:
                prompt = input("\n[You] > ").strip()

                if not prompt:
                    continue

                # コマンド処理
                if prompt.startswith("/"):
                    should_exit = await handle_command(prompt, browser)
                    if should_exit:
                        break
                    continue

                # プロンプト送信
                await browser.send_prompt(prompt)

                # レスポンス取得
                response = await browser.wait_for_response()
                print(f"\n[ChatGPT]\n{response}")

            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                logger.error(f"Error: {e}")

    logger.info("Goodbye!")


def print_interactive_help() -> None:
    """対話モードのヘルプを表示"""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                    Wagent Interactive Mode                   ║
╠══════════════════════════════════════════════════════════════╣
║  Commands:                                                   ║
║    /new         - Start a new chat                           ║
║    /screenshot  - Take a screenshot                          ║
║    /status      - Check login status                         ║
║    /help        - Show this help                             ║
║    /quit        - Exit interactive mode                      ║
║                                                              ║
║  Enter your prompt and press Enter to send.                  ║
║  Press Ctrl+C to exit.                                       ║
╚══════════════════════════════════════════════════════════════╝
"""
    )


async def handle_command(command: str, browser: BrowserController) -> bool:
    """
    コマンドを処理

    Returns:
        終了する場合はTrue
    """
    cmd = command.lower().strip()

    if cmd in ("/quit", "/exit", "/q"):
        return True

    if cmd == "/new":
        await browser.new_chat()
        logger.info("Started new chat")
        return False

    if cmd == "/screenshot":
        path = await browser.screenshot()
        logger.info(f"Screenshot saved: {path}")
        return False

    if cmd == "/status":
        logged_in = await browser.is_logged_in()
        status = "Logged in ✓" if logged_in else "Not logged in ✗"
        print(f"Status: {status}")
        return False

    if cmd == "/help":
        print_interactive_help()
        return False

    logger.warning(f"Unknown command: {command}")
    return False


# =============================================================================
# サーバーモード
# =============================================================================


def run_server_mode(host: str, port: int) -> None:
    """サーバーモードで実行"""
    from wagent.config import Config
    from wagent.server import run_server

    config = Config.load()
    setup_logging(config.logging.level, config.logging.file)

    # ディレクトリ作成
    Path("logs").mkdir(exist_ok=True)
    Path("screenshots").mkdir(exist_ok=True)
    Path(config.browser.user_data_dir).mkdir(exist_ok=True)

    run_server(host=host, port=port)


# =============================================================================
# メインエントリーポイント
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """引数パーサーを作成"""
    parser = argparse.ArgumentParser(
        prog="wagent",
        description="Wagent - ChatGPT Web UI Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start API server
  wagent --server
  wagent --server --host 0.0.0.0 --port 9000

  # Start interactive mode (for initial login)
  wagent --interactive

  # Show version
  wagent --version
        """,
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "-s",
        "--server",
        action="store_true",
        help="Start API server mode",
    )
    mode_group.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start interactive mode (for login and testing)",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Server port (default: 8765)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (override config)",
    )

    return parser


def get_version() -> str:
    """バージョンを取得"""
    from wagent import __version__

    return __version__


def main() -> NoReturn | None:
    """メインエントリーポイント"""
    parser = create_parser()
    args = parser.parse_args()

    # ヘッドレスモードのオーバーライド
    if args.headless:
        import os

        os.environ["WAGENT_HEADLESS"] = "true"

    try:
        if args.server:
            run_server_mode(args.host, args.port)
        elif args.interactive:
            asyncio.run(run_interactive_mode())

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

    return None


if __name__ == "__main__":
    main()
