from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.correlation import generate_correlation_id, set_correlation_id

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if X-Correlation-ID is provided in the headers
        correlation_id = request.headers.get("X-Correlation-ID")
        
        # If not provided or empty, generate a new one
        if not correlation_id:
            correlation_id = generate_correlation_id()
        else:
            # Apply reasonable length constraint to prevent abuse
            correlation_id = correlation_id[:255]
            
        set_correlation_id(correlation_id)
        
        response = await call_next(request)
        
        # Also include it in the response headers for tracing
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
