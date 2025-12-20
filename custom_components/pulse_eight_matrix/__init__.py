"""The Pulse Eight HDBaseT Matrix integration."""
from __future__ import annotations

import logging
from typing import Any

from pulse_eight_matrix_client import CachingPulseEightMatrixClient
from pulse_eight_matrix_client.exceptions import PulseEightConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pulse Eight Matrix from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    #session = async_get_clientsession(hass)

    client = CachingPulseEightMatrixClient(
        host=host,
        port=port,
        poll_interval=poll_interval,
        #session=session,
    )

    try:
        await client.connect()
        # Verify connection by getting system details
        system_details = await client.get_system_details()
        _LOGGER.info(
            "Connected to Pulse Eight Matrix: %s (v%s)",
            system_details.model,
            system_details.version,
        )
    except PulseEightConnectionError as err:
        await client.close()
        raise ConfigEntryNotReady(f"Could not connect to {host}:{port}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "system_details": system_details,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client = data["client"]
        await client.close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
