"""Task-Oriented Memory Compilation for long-context language models."""

from .automatic_chat import AutomaticChatSession
from .compiler import STRATEGIES, compile_memory
from .easy import PreparedContext, prepare_context
from .model_profiles import ModelProfile, get_model_profile
from .request_context import RequestContextManager, RequestContextPlan
from .schemas import CompilationResult, CompilationStats, LedgerRecord, Message, Source

__version__ = "0.1.0"
__all__ = [
    "AutomaticChatSession",
    "RequestContextManager",
    "RequestContextPlan",
    "ModelProfile",
    "get_model_profile",
    "compile_memory",
    "prepare_context",
    "PreparedContext",
    "STRATEGIES",
    "Message",
    "CompilationResult",
    "CompilationStats",
    "LedgerRecord",
    "Source",
]
