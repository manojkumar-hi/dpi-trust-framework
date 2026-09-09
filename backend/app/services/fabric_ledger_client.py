from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from app.core.config import get_settings


class FabricLedgerUnavailableError(Exception):
    """Raised when the Fabric adapter cannot be reached or is unavailable."""


class FabricLedgerOperationError(Exception):
    """Raised when the Fabric adapter returns an operation or response error."""


class FabricLedgerClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client or httpx.AsyncClient(
            base_url=settings.fabric_adapter_url.rstrip("/"),
            timeout=settings.fabric_adapter_timeout_seconds,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def issue_credential(
        self,
        credential_id: UUID | str,
        credential_type: str,
        issuer_did: str,
        subject_did: str,
        credential_hash: str,
        issued_at: datetime | str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/internal/credentials/issue",
            json={
                "credentialId": _wire_value(credential_id),
                "credentialType": credential_type,
                "issuerDid": issuer_did,
                "subjectDid": subject_did,
                "credentialHash": credential_hash,
                "issuedAt": _wire_value(issued_at),
            },
        )

    async def read_credential(self, credential_id: UUID | str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/credentials/{_path_value(credential_id)}",
        )

    async def verify_credential(
        self,
        credential_id: UUID | str,
        credential_hash: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/credentials/{_path_value(credential_id)}/verify",
            json={"credentialHash": credential_hash},
        )

    async def revoke_credential(
        self,
        credential_id: UUID | str,
        reason: str,
        revoked_at: datetime | str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/credentials/{_path_value(credential_id)}/revoke",
            json={
                "reason": reason,
                "revokedAt": _wire_value(revoked_at),
            },
        )

    async def get_credential_history(
        self,
        credential_id: UUID | str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/internal/credentials/{_path_value(credential_id)}/history",
        )

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise FabricLedgerUnavailableError(
                "Fabric adapter request timed out"
            ) from exc
        except httpx.RequestError as exc:
            raise FabricLedgerUnavailableError(
                f"Fabric adapter is unavailable: {exc}"
            ) from exc

        payload = _parse_response(response)
        if response.status_code == 503:
            raise FabricLedgerUnavailableError(_error_message(payload, response))
        if response.is_error:
            raise FabricLedgerOperationError(_error_message(payload, response))
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise FabricLedgerOperationError(
                _error_message(payload, response)
            )
        if "result" not in payload:
            raise FabricLedgerOperationError(
                "Fabric adapter returned an invalid success response"
            )
        if "transaction_id" not in payload:
            payload["transaction_id"] = None
        return payload


def _wire_value(value: Any) -> Any:
    if isinstance(value, (datetime, UUID)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    return value


def _path_value(value: Any) -> str:
    return quote(str(value), safe="")


def _parse_response(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise FabricLedgerOperationError(
            f"Fabric adapter returned invalid JSON (HTTP {response.status_code})"
        ) from exc


def _error_message(payload: Any, response: httpx.Response) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        if isinstance(error, str) and error:
            return error
    return f"Fabric adapter request failed with HTTP {response.status_code}"