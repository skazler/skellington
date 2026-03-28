"""Skellington agents — the Halloween-ized Christmas characters."""

from skellington.agents.jack import Jack
from skellington.agents.mayor import Mayor
from skellington.agents.oogie import Oogie
from skellington.agents.sally import Sally
from skellington.agents.validators import Barrel, Lock, Shock, ValidatorCoordinator
from skellington.agents.zero import Zero

__all__ = [
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
