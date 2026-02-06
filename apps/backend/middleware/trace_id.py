"""Single source for request trace_id. Use scope for ASGI, request.scope for Starlette."""
import uuid

SCOPE_KEY = "trace_id"


def ensure_trace_id(scope: dict) -> str:
    """Get or set trace_id on ASGI scope. Returns the same trace_id for the request lifecycle."""
    tid = scope.get(SCOPE_KEY)
    if tid and isinstance(tid, str):
        return tid
    tid = str(uuid.uuid4())[:16]
    scope[SCOPE_KEY] = tid
    return tid
