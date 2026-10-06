"""Built-in strategies and extension protocol."""

from .agent import TOMC2Strategy
from .base import CompressionStrategy, StrategyOutput
from .baselines import RawStrategy, RetrievalStrategy, TruncationStrategy
from .typed import TOMCStrategy

__all__ = [
    "CompressionStrategy",
    "StrategyOutput",
    "RawStrategy",
    "TruncationStrategy",
    "RetrievalStrategy",
    "TOMCStrategy",
    "TOMC2Strategy",
]
