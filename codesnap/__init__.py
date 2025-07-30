"""
codesnap - Generate LLM-friendly code snapshots.

A CLI tool to create clean, structured snapshots of your codebase
optimized for use with Large Language Models.
"""

__version__ = "1.0.0"
__author__ = "Henning Krause"
__email__ = "henning.krause90@googlemail.com"

from codesnap.core import CodeSnapshotter
from codesnap.config import Config, Language

__all__ = ["CodeSnapshotter", "Config", "Language"]
