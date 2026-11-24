"""Toplo.bg Home Assistant integration."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ToploApi
from .const import DOMAIN, UPDATE_INTERVAL_MINUTES

ToploConfigEntry = ConfigEntry[DataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ToploConfigEntry) -> bool:
    """Set up Toplo.bg from a config entry."""
    api = ToploApi(
        async_get_clientsession(hass),
        entry.data["email"],
        entry.data["password"],
    )
    coordinator = DataUpdateCoordinator(
        hass,
        logger=logging.getLogger(__name__),
        config_entry=entry,
        name=DOMAIN,
        update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        update_method=api.async_get_data,
        always_update=False,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ToploConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
