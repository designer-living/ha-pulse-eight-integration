"""Config flow for the Pulse8 HDBaseT Matrix integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_POLL_INTERVAL, DEFAULT_PORT, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class Pulse8ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pulse8 Matrix."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            # Test connection
            try:
                from pulse_eight_matrix_client import PulseEightMatrixClient


                async with PulseEightMatrixClient(host=host, port=port) as client:
                    details = await client.get_system_details()

                # Set unique ID based on serial number
                await self.async_set_unique_id(details.serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Pulse8 {details.model}",
                    data=user_input,
                )
            except Exception as err:
                _LOGGER.error("Failed to connect to Pulse8 Matrix: %s", err)
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
