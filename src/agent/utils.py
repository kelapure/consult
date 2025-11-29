from functools import wraps
from loguru import logger

def handle_tool_errors(tool_func):
    """
    A decorator to handle errors in tool functions.
    It logs the error with a correlation ID and returns a standardized error response.
    """
    @wraps(tool_func)
    async def wrapper(args: dict, **kwargs):
        from src.agent.consult_agent import agent_ctx # Defer import to avoid circular dependency
        
        correlation_id = "N/A"
        if agent_ctx:
            correlation_id = agent_ctx.correlation_id

        try:
            return await tool_func(args, **kwargs)
        except Exception as e:
            error_message = f"An unexpected error occurred in {tool_func.__name__}: {e}"
            logger.error(f"[{correlation_id}] {error_message}")
            
            # Optionally, record the failure to metrics
            if agent_ctx and agent_ctx.metrics:
                agent_ctx.metrics.record_failure(
                    failure_type="tool_error",
                    component=tool_func.__name__,
                    reason=str(e),
                    context={"args": args}
                )

            return {
                "content": [{"type": "text", "text": f"Error: {error_message}"}],
                "is_error": True,
            }
    return wrapper
