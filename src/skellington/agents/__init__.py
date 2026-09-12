"""Skellington agents — the Halloween-ized Christmas characters."""

from skellington.agents.jack import Jack
from skellington.agents.mayor import Mayor
from skellington.agents.oogie import Oogie
from skellington.agents.sally import Sally
from skellington.agents.validators import Barrel, Lock, Shock, ValidatorCoordinator
from skellington.agents.zero import Zero


def default_agents() -> list[object]:
    """Build one fresh instance of every agent, for handing to an Orchestrator.

    Callers get their own instances, so two orchestrators never share state.
    Keep this as the single definition of "all the agents" — the CLI and the
    web UI each used to hand-roll the list and both silently omitted the
    validators.
    """
    return [cls() for cls in (Jack, Sally, Oogie, Zero, Lock, Shock, Barrel, Mayor)]


__all__ = [
    "default_agents",
    "Jack",
    "Sally",
    "Oogie",
    "Zero",
    "Lock",
    "Shock",
    "Barrel",
    "ValidatorCoordinator",
    "Mayor",
]
