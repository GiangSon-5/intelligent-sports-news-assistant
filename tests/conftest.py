"""
conftest.py — Shared pytest fixtures cho toàn bộ test suite.
"""

import os
import sys

# Đảm bảo project root trong sys.path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Đảm bảo crawler root cho Scrapy imports
_crawler_root = os.path.join(_project_root, "crawler")
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)
