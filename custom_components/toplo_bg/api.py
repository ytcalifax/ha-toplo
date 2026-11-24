"""Async client for the Toplo.bg API."""

from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import BASE_URL


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
        """Make an API request without logging sensitive response data."""
        try:
            async with self._session.request(
                "POST" if json is not None else "GET",
                f"{BASE_URL}/{path}",
                params=params,
                json=json,
                headers={
                    "accept": "application/json",
                    **({"authorization": f"Bearer {self._token}"} if self._token else {}),
                },
                timeout=30,
            ) as response:
                if response.status == 401:
                    raise ConfigEntryAuthFailed("Toplo.bg rejected the credentials")
                response.raise_for_status()
                return await response.json()
        except ConfigEntryAuthFailed:
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            raise ConfigEntryNotReady(
                f"Toplo.bg request failed for {path}"
            ) from err

    @staticmethod
    def _object(payload: Any, endpoint: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigEntryNotReady(f"Invalid Toplo.bg response from {endpoint}")
        return payload

    @staticmethod
    def _list(payload: Any, endpoint: str) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            payload = payload.get("$values")
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
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
            raise ConfigEntryAuthFailed("Toplo.bg login failed")
        self._token = result["token"]

    async def async_validate(self) -> dict[str, Any]:
        """Check credentials and profile access during setup."""
        await self.async_login()
        profile = self._object(await self._request("profile/get"), "profile/get")
        if not profile.get("id"):
            raise ConfigEntryNotReady("Toplo.bg returned no profile ID")
        return profile

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch all current account and installation data."""
        await self.async_login()
        profile = self._object(await self._request("profile/get"), "profile/get")
        profile_id = profile.get("id")
        if not profile_id:
            raise ConfigEntryNotReady("Toplo.bg returned no profile ID")

        installations = self._list(
            await self._request(
                "installations/getbyuserid", params={"userId": profile_id}
            ),
            "installations/getbyuserid",
        )
        now = datetime.now(timezone.utc)
        year = now.year
        start = f"{year}-01-01T00:00:00Z"
        end = f"{year}-12-31T23:59:59Z"
        account_data: dict[str, Any] = {"profile": profile, "installations": []}

        for installation in installations:
            installation_id = installation.get("id")
            if not installation_id:
                raise ConfigEntryNotReady("Toplo.bg returned an installation without an ID")
            date_params = {
                "installationId": installation_id,
                "fromDate": start,
                "toDate": end,
            }
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
                raise ConfigEntryNotReady("Toplo.bg could not load invoices")
            invoice_item = self._object(invoices_response.get("item"), "invoices/getAll.item")
            account_data["installations"].append(
                {
                    **installation,
                    "invoices": self._list(invoice_item, "invoices/getAll.item"),
                    "consumption": self._list(
                        await self._request("energyConsumption/get", params=date_params),
                        "energyConsumption/get",
                    ),
                    "station": self._list(
                        await self._request(
                            "energyConsumptionStation/get", params=date_params
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
