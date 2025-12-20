"""Select platform for Pulse Eight Matrix routing."""
from __future__ import annotations

import logging
from typing import Any

from pulse_eight_matrix_client import CachingPulseEightMatrixClient
from pulse_eight_matrix_client.exceptions import PulseEightAPIError, PulseEightConnectionError
from pulse_eight_matrix_client.models import Port

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pulse Eight Matrix select entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: CachingPulseEightMatrixClient = data["client"]
    system_details = data["system_details"]

    ports = await client.get_ports()
    inputs = [port for port in ports if port.mode == "Input"]
    outputs = [port for port in ports if port.mode == "Output"]

    entities = [
        PulseEightMatrixOutputSelect(
            client=client,
            output=output,
            inputs=inputs,
            system_details=system_details,
            config_entry=config_entry,
        )
        for output in outputs
    ]
    async_add_entities(entities)


class PulseEightMatrixOutputSelect(SelectEntity):
    """Select entity for routing an output to an input."""

    _attr_has_entity_name = True

    def __init__(
        self,
        client: CachingPulseEightMatrixClient,
        output: Port,
        inputs: list[Port],
        system_details: Any,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        self._client = client
        self._output = output
        self._inputs = inputs
        self._system_details = system_details
        self._config_entry = config_entry

        self._attr_unique_id = f"{system_details.serial}_select_{output.bay}"
        self._attr_name = f"{output.name or f'Output {output.bay}'} Input"
        self._attr_translation_key = "input_source"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_details.serial)},
            name=f"Pulse Eight {system_details.model}",
            manufacturer=MANUFACTURER,
            model=system_details.model,
            sw_version=system_details.version,
            configuration_url=f"http://{config_entry.data[CONF_HOST]}:{config_entry.data.get(CONF_PORT, 80)}",
        )
        self._current_source_bay: int | None = None

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            self._current_source_bay = self._client.get_cached_output_source(self._output.bay)
        except (PulseEightAPIError, PulseEightConnectionError) as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)
            self._current_source_bay = None

    @property
    def current_option(self) -> str | None:
        """Return the current input source."""
        if self._current_source_bay is not None:
            for inp in self._inputs:
                if inp.bay == self._current_source_bay:
                    return inp.name or f"Input {inp.bay}"
        return None

    @property
    def options(self) -> list[str]:
        """Return available input sources."""
        return [inp.name or f"Input {inp.bay}" for inp in self._inputs]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        input_port = next(
            (
                inp
                for inp in self._inputs
                if (inp.name or f"Input {inp.bay}") == option
            ),
            None,
        )

        if input_port is None:
            _LOGGER.error("Input source %s not found", option)
            return

        try:
            await self._client.set_port(input_port.bay, self._output.bay)
            self.async_write_ha_state()
        except (PulseEightAPIError, PulseEightConnectionError) as err:
            _LOGGER.error("Failed to set source: %s", err)