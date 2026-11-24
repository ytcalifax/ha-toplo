"""Async client for the Toplo.bg API."""

import json
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import BASE_URL
from .diagnostics import (
    log_api_failure,
    log_application_error,
    log_invalid_shape,
    log_login_rejected,
    response_diagnostics,
)


class ToploApi:
    """Fetch account and installation data from Toplo.bg."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make an API request and log failures without request secrets."""
        method = "POST" if json is not None else "GET"
        response = None
        try:
            async with self._session.request(
                method,
                f"{BASE_URL}/{path}",
                params=params,
                json=json,
                headers={
                    "accept": "application/json",
                    **({"authorization": f"Bearer {self._token}"} if self._token else {}),
                },
                timeout=30,
            ) as response:
                if response.status >= 400:
                    details, body_size = await self._error_response_details(response)
                    log_api_failure(
                        method=method,
                        endpoint=path,
                        params=params,
                        status=response.status,
                        content_type=response.content_type,
                        response_bytes=body_size,
                        diagnostics=details,
                    )
                    if response.status == 401:
                        raise ConfigEntryAuthFailed("Toplo.bg rejected the credentials")
                    raise ConfigEntryNotReady(
                        f"Toplo.bg request failed for {path} (HTTP {response.status})"
                    )
                return await response.json()
        except (ConfigEntryAuthFailed, ConfigEntryNotReady):
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            log_api_failure(
                method=method,
                endpoint=path,
                params=params,
                status=response.status if response is not None else None,
                content_type=response.content_type if response is not None else None,
                error=err,
            )
            raise ConfigEntryNotReady(
                f"Toplo.bg request failed for {path} ({type(err).__name__})"
            ) from err
        except Exception as err:
            log_api_failure(
                method=method,
                endpoint=path,
                params=params,
                status=response.status if response is not None else None,
                content_type=response.content_type if response is not None else None,
                error=err,
            )
            raise ConfigEntryNotReady(
                f"Unexpected Toplo.bg request failure for {path} ({type(err).__name__})"
            ) from err

    @staticmethod
    async def _error_response_details(response: Any) -> tuple[dict[str, Any], int]:
        """Read a bounded error body and extract safe metadata, never body text."""
        try:
            body = await response.content.read(8193)
        except (ClientError, TimeoutError) as err:
            return {"body_read_error": type(err).__name__}, 0

        truncated = len(body) > 8192
        body = body[:8192]
        if not body:
            return {"body": "empty", "truncated": False}, 0
        try:
            payload = json.loads(body.decode(response.charset or "utf-8", "replace"))
        except (UnicodeError, ValueError):
            return {"body_format": "non_json", "truncated": truncated}, len(body)
        details = response_diagnostics(payload)
        details["truncated"] = truncated
        return details, len(body)

    @staticmethod
    def _object(payload: Any, endpoint: str) -> dict[str, Any]:
        """Require an API object response."""
        if not isinstance(payload, dict):
            log_invalid_shape(endpoint, "object", payload)
            raise ConfigEntryNotReady(f"Invalid Toplo.bg response from {endpoint}")
        return payload

    @staticmethod
    def _list(payload: Any, endpoint: str) -> list[dict[str, Any]]:
        """Require a list response, including the API's $values envelope."""
        original_payload = payload
        if isinstance(payload, dict):
            payload = payload.get("$values")
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            log_invalid_shape(endpoint, "list of objects", original_payload)
            raise ConfigEntryNotReady(f"Invalid Toplo.bg list from {endpoint}")
        return payload

    async def async_login(self) -> None:
        """Get a fresh access token."""
        result = self._object(
            await self._request(
                "auth/login", json={"Email": self._email, "Password": self._password}
            ),
            "auth/login",
        )
        if not result.get("isSuccess") or not result.get("token"):
            log_login_rejected(result)
            raise ConfigEntryAuthFailed("Toplo.bg login failed")
        self._token = result["token"]

    async def async_validate(self) -> dict[str, Any]:
        """Check credentials and profile access during setup."""
        await self.async_login()
        profile = self._object(await self._request("profile/get"), "profile/get")
        if not profile.get("id"):
            log_invalid_shape("profile/get", "object with profile ID", profile)
            raise ConfigEntryNotReady("Toplo.bg returned no profile ID")
        return profile

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch all current account and installation data."""
        await self.async_login()
        profile = self._object(await self._request("profile/get"), "profile/get")
        profile_id = profile.get("id")
        if not profile_id:
            log_invalid_shape("profile/get", "object with profile ID", profile)
            raise ConfigEntryNotReady("Toplo.bg returned no profile ID")

        installations = self._list(
            await self._request(
                "installations/getbyuserid", params={"userId": profile_id}
            ),
            "installations/getbyuserid",
        )
        year = datetime.now(timezone.utc).year
        date_params = {
            "fromDate": f"{year}-01-01T00:00:00Z",
            "toDate": f"{year}-12-31T23:59:59Z",
        }
        account_data: dict[str, Any] = {"profile": profile, "installations": []}

        for installation in installations:
            installation_id = installation.get("id")
            if not installation_id:
                log_invalid_shape(
                    "installations/getbyuserid",
                    "installation object with ID",
                    installation,
                )
                raise ConfigEntryNotReady("Toplo.bg returned an installation without an ID")

            installation_params = {"installationId": installation_id, **date_params}
            invoices_response = self._object(
                await self._request(
                    "invoices/getAll",
                    params={
                        "installationIds": installation_id,
                        "invoicePeriodFilter": 24,
                    },
                ),
                "invoices/getAll",
            )
            if invoices_response.get("isSuccessStatusCode") is False:
                log_application_error("invoices/getAll", invoices_response)
                raise ConfigEntryNotReady("Toplo.bg could not load invoices")
            invoice_item = self._object(invoices_response.get("item"), "invoices/getAll.item")

            account_data["installations"].append(
                {
                    **installation,
                    "invoices": self._list(invoice_item, "invoices/getAll.item"),
                    "consumption": self._list(
                        await self._request(
                            "energyConsumption/get", params=installation_params
                        ),
                        "energyConsumption/get",
                    ),
                    "station": self._list(
                        await self._request(
                            "energyConsumptionStation/get", params=installation_params
                        ),
                        "energyConsumptionStation/get",
                    ),
                    "aligning": self._list(
                        await self._request(
                            "annualAligning/get",
                            params={
                                "installationId": installation_id,
                                "fromYear": year,
                                "toYear": year,
                            },
                        ),
                        "annualAligning/get",
                    ),
                }
            )
        return account_data
