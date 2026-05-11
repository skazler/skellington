"""Sally's skills package."""

from skellington.agents.sally.skills.imports import SCHEMA as OPTIMIZE_IMPORTS_SCHEMA
from skellington.agents.sally.skills.imports import optimize_imports
from skellington.agents.sally.skills.styling import SCHEMA as CHECK_CODE_STYLE_SCHEMA
from skellington.agents.sally.skills.styling import check_code_style
from skellington.agents.sally.skills.testing import SCHEMA as GENERATE_UNIT_TESTS_SCHEMA
from skellington.agents.sally.skills.testing import generate_unit_tests

__all__ = [
    "generate_unit_tests",
    "GENERATE_UNIT_TESTS_SCHEMA",
    "check_code_style",
    "CHECK_CODE_STYLE_SCHEMA",
    "optimize_imports",
    "OPTIMIZE_IMPORTS_SCHEMA",
]
