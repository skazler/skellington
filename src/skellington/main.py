"""
Skellington entry point.

`skellington` CLI command maps here via pyproject.toml [project.scripts].
"""

from skellington.ui.cli import app

if __name__ == "__main__":
    app()
