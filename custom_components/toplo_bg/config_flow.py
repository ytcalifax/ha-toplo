"""Config flow for Toplo.bg."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ToploApi
from .const import CONF_OWNER, DOMAIN

class ToploConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure and reauthenticate a Toplo.bg account."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry = None
        self._reauth_email = ""

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Add a Toplo.bg account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input["email"].strip()
            await self.async_set_unique_id(email.casefold())
            self._abort_if_unique_id_configured()
            try:
                profile = await self._validate(user_input)
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except ConfigEntryNotReady:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_OWNER].strip() or profile.get("name") or "Toplo.bg",
                    data={**user_input, "email": email, CONF_OWNER: user_input[CONF_OWNER].strip()},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("email"): str,
                    vol.Required("password"): str,
                    vol.Optional(CONF_OWNER, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Start credential renewal after an authentication failure."""
        self._reauth_entry = self._get_reauth_entry()
        self._reauth_email = entry_data["email"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, str] | None = None):
        """Ask for current credentials and update the existing entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input["email"].strip()
            await self.async_set_unique_id(email.casefold())
            self._abort_if_unique_id_mismatch()
            try:
                await self._validate(user_input)
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except ConfigEntryNotReady:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={
                        "email": email,
                        "password": user_input["password"],
                        CONF_OWNER: user_input[CONF_OWNER].strip(),
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("email", default=self._reauth_email): str,
                    vol.Required("password"): str,
                    vol.Optional(
                        CONF_OWNER,
                        default=self._reauth_entry.data.get(CONF_OWNER, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={"name": self._reauth_entry.title},
        )

    async def _validate(self, user_input: dict[str, str]) -> dict[str, Any]:
        """Verify credentials without exposing them in logs."""
        api = ToploApi(
            async_get_clientsession(self.hass),
            user_input["email"].strip(),
            user_input["password"],
        )
        return await api.async_validate()
