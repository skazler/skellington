"""Oogie's skills package."""

from skellington.agents.oogie.skills.analysis import SCHEMA as ANALYZE_TRENDS_SCHEMA
from skellington.agents.oogie.skills.analysis import analyze_trends
from skellington.agents.oogie.skills.search import SCHEMA as WEB_SEARCH_SCHEMA
from skellington.agents.oogie.skills.search import web_search
from skellington.agents.oogie.skills.summarization import SCHEMA as SUMMARIZE_FINDINGS_SCHEMA
from skellington.agents.oogie.skills.summarization import summarize_findings

__all__ = [
    "web_search",
    "WEB_SEARCH_SCHEMA",
    "analyze_trends",
    "ANALYZE_TRENDS_SCHEMA",
    "summarize_findings",
    "SUMMARIZE_FINDINGS_SCHEMA",
]
