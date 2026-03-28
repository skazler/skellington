"""Skellington subagents — focused, single-purpose workers spawned by main agents."""

from skellington.subagents.codegen import CodeGenSubagent
from skellington.subagents.compare import CompareSubagent
from skellington.subagents.context import ContextSubagent
from skellington.subagents.dependency import DependencySubagent
from skellington.subagents.diff import DiffSubagent
from skellington.subagents.file_explorer import FileExplorerSubagent
from skellington.subagents.formatter import FormatSubagent
from skellington.subagents.lint import LintSubagent
from skellington.subagents.planner import PlannerSubagent
from skellington.subagents.refactor import RefactorSubagent
from skellington.subagents.router import RouterSubagent
from skellington.subagents.scaffold import ScaffoldSubagent
from skellington.subagents.search import SearchSubagent
from skellington.subagents.security import SecuritySubagent
from skellington.subagents.status import StatusSubagent
from skellington.subagents.summary import SummarySubagent
from skellington.subagents.test_runner import TestSubagent

__all__ = [
    "PlannerSubagent",
    "RouterSubagent",
    "CodeGenSubagent",
    "RefactorSubagent",
    "ScaffoldSubagent",
    "SearchSubagent",
    "SummarySubagent",
    "CompareSubagent",
    "FileExplorerSubagent",
    "DependencySubagent",
    "ContextSubagent",
    "LintSubagent",
    "TestSubagent",
    "SecuritySubagent",
    "FormatSubagent",
    "DiffSubagent",
    "StatusSubagent",
]
