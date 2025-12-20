"""Support for Pulse Eight HDBaseT Matrix as media players."""
from __future__ import annotations

import logging
from typing import Any

from pulse_eight_matrix_client import CachingPulseEightMatrixClient
from pulse_eight_matrix_client.exceptions import PulseEightAPIError, PulseEightConnectionError
from pulse_eight_matrix_client.models import Port

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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
    """Set up Pulse Eight Matrix media player entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: CachingPulseEightMatrixClient = data["client"]
    system_details = data["system_details"]

    # Get all ports
    ports = await client.get_ports()

    # Get inputs and outputs
    inputs = [port for port in ports if port.mode == "Input"]
    outputs = [port for port in ports if port.mode == "Output"]

    # Create media player entities for each output
    entities = [
        PulseEightMatrixOutput(
            client=client,
            output=output,
            inputs=inputs,
            system_details=system_details,
            config_entry=config_entry,
        )
        for output in outputs
    ]

    async_add_entities(entities)


class PulseEightMatrixOutput(MediaPlayerEntity):
    """Representation of a Pulse Eight Matrix output as a media player."""

    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE

    def __init__(
            self,
            client: CachingPulseEightMatrixClient,
            output: Port,
            inputs: list[Port],
            system_details: Any,
            config_entry: ConfigEntry,
    ) -> None:
        """Initialize the media player."""
        self._client = client
        self._output = output
        self._inputs = inputs
        self._system_details = system_details
        self._config_entry = config_entry

        # Entity attributes
        self._attr_unique_id = f"{system_details.serial}_output_{output.bay}"
        self._attr_name = output.name or f"Output {output.bay}"

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_details.serial)},
            name=f"Pulse Eight {system_details.model}",
            manufacturer=MANUFACTURER,
            model=system_details.model,
            sw_version=system_details.version,
            configuration_url=f"http://{config_entry.data[CONF_HOST]}:{config_entry.data.get(CONF_PORT, 80)}",
        )

        # Source list (input names)
        self._attr_source_list = [
            inp.name or f"Input {inp.bay}" for inp in inputs
        ]

        # Current state
        self._current_source: str | None = None
        self._state = MediaPlayerState.IDLE

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            # Get current routing from cache
            source_bay = self._client.get_cached_output_source(self._output.bay)

            if source_bay is not None:
                # Find the input port
                source_port = next(
                    (inp for inp in self._inputs if inp.bay == source_bay),
                    None,
                )
                if source_port:
                    self._current_source = source_port.name or f"Input {source_port.bay}"

                    # Check if there's a signal
                    try:
                        output_details = await self._client.get_output_details(self._output.bay)
                        self._state = (
                            MediaPlayerState.PLAYING
                            if output_details.has_signal
                            else MediaPlayerState.IDLE
                        )
                    except (PulseEightAPIError, PulseEightConnectionError):
                        self._state = MediaPlayerState.ON
                else:
                    self._current_source = None
                    self._state = MediaPlayerState.IDLE
            else:
                self._current_source = None
                self._state = MediaPlayerState.IDLE

        except (PulseEightAPIError, PulseEightConnectionError) as err:
            _LOGGER.error("Error updating %s: %s", self.name, err)
            self._state = MediaPlayerState.UNAVAILABLE

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        return self._state

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._current_source

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        # Find the input port by name
        input_port = next(
            (
                inp
                for inp in self._inputs
                if (inp.name or f"Input {inp.bay}") == source
            ),
            None,
        )

        if input_port is None:
            _LOGGER.error("Source %s not found", source)
            return

        try:
            await self._client.set_port(
                input_bay=input_port.bay,
                output_bay=self._output.bay,
            )
            self._current_source = source
            self._state = MediaPlayerState.ON
            self.async_write_ha_state()
        except (PulseEightAPIError, PulseEightConnectionError) as err:
            _LOGGER.error("Error setting source for %s: %s", self.name, err)
