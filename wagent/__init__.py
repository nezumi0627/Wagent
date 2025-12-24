"""
Wagent - Web-Agent Bridge for ChatGPT
=====================================

Web版ChatGPTをAPI的に利用するためのブリッジツール。
Playwrightによるブラウザ自動化を使用。

Author: nezumi0627
License: MIT
"""

__version__ = "0.1.0"
__author__ = "nezumi0627"
__license__ = "MIT"

from wagent.browser import BrowserController
from wagent.client import WagentClient
from wagent.config import Config

__all__ = [
    "__version__",
    "__author__",
    "Config",
    "BrowserController",
    "WagentClient",
]
