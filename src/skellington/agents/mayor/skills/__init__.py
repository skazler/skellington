"""Mayor's skills package."""

from skellington.agents.mayor.skills.documentation import SCHEMA as GENERATE_DOCUMENTATION_SCHEMA
from skellington.agents.mayor.skills.documentation import generate_documentation
from skellington.agents.mayor.skills.formatting import SCHEMA as FORMAT_REPORTS_SCHEMA
from skellington.agents.mayor.skills.formatting import format_reports
from skellington.agents.mayor.skills.visualization import SCHEMA as CREATE_VISUALIZATIONS_SCHEMA
from skellington.agents.mayor.skills.visualization import create_visualizations

__all__ = [
    "generate_documentation",
    "GENERATE_DOCUMENTATION_SCHEMA",
    "create_visualizations",
    "CREATE_VISUALIZATIONS_SCHEMA",
    "format_reports",
    "FORMAT_REPORTS_SCHEMA",
]
