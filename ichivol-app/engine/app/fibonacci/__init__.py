"""Fibonacci Context — retracement levels from Market Structure swings.

Not part of Market Structure geometry. Fib measures retracement inside
an already-found swing (docs/ARCHITECTURE-CONSOLIDEE-V2.md §6).
"""

from app.fibonacci.context import FIB_RATIOS, FibContext, FibLevel, compute_fib_context
from app.fibonacci.gate import FibonacciGateResult, apply_fibonacci_gate

__all__ = [
    "FIB_RATIOS",
    "FibContext",
    "FibLevel",
    "FibonacciGateResult",
    "apply_fibonacci_gate",
    "compute_fib_context",
]
