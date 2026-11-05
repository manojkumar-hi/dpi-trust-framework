import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.authorization import AuthorizationDecision
from app.services.authorization_engine import AuthorizationEngine

logger = logging.getLogger(__name__)


async def evaluate_with_opa(input_data: dict[str, Any]) -> AuthorizationDecision:
    settings = get_settings()
    url = f"{settings.opa_url.rstrip('/')}/v1/data/dpi/authz/decision"
    try:
        async with httpx.AsyncClient(timeout=settings.opa_timeout_seconds) as client:
            response = await client.post(url, json={"input": input_data})
            if response.status_code == 200:
                result = response.json().get("result")
                if isinstance(result, dict):
                    return AuthorizationDecision.model_validate(result)
                logger.warning("OPA returned 200 but result payload is missing or invalid: %s", response.text)
            else:
                logger.warning(
                    "OPA returned status %s for url '%s': %s. Falling back to local AuthorizationEngine.",
                    response.status_code,
                    url,
                    response.text,
                )
    except Exception as exc:
        logger.warning(
            "OPA request to '%s' failed: %s. Falling back to local AuthorizationEngine.",
            url,
            exc,
        )

    # Resilient fallback: evaluate using the built-in pure Python AuthorizationEngine
    return AuthorizationEngine.evaluate(input_data)
