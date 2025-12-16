"""Support for Pulse Eight HDBaseT Matrix as media players."""
from __future__ import annotations

import logging
from typing import Any

from pulse_eight_matrix_client import PulseEightMatrixClient
from pulse_eight_matrix_client.exceptions import Pulse8APIError, Pulse8ConnectionError
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
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pulse Eight Matrix media player entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: Pulse8MatrixClient = data["client"]
    coordinator: DataUpdateCoordinator = data["coordinator"]
    system_details = data["system_details"]

    # Get outputs from coordinator data
    outputs = coordinator.data["outputs"]
    inputs = coordinator.data["inputs"]

    # Create media player entities for each output
    entities = [
        PulseEightMatrixOutput(
            coordinator=coordinator,
            client=client,
            output=output,
            inputs=inputs,
            system_details=system_details,
            config_entry=config_entry,
        )
        for output in outputs
    ]

    async_add_entities(entities)


class PulseEightMatrixOutput(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Pulse Eight Matrix output as a media player."""

    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE

    def __init__(
            self,
            coordinator: DataUpdateCoordinator,
            client: Pulse8MatrixClient,
            output: Port,
            inputs: list[Port],
            system_details: Any,
            config_entry: ConfigEntry,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)

        self._client = client
        self._output_bay = output.bay
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

    @property
    def _output(self) -> Port | None:
        """Get current output port from coordinator data."""
        outputs = self.coordinator.data.get("outputs", [])
        return next((o for o in outputs if o.bay == self._output_bay), None)

    @property
    def _inputs(self) -> list[Port]:
        """Get inputs from coordinator data."""
        return self.coordinator.data.get("inputs", [])

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return [inp.name or f"Input {inp.bay}" for inp in self._inputs]

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        if not self.coordinator.last_update_success:
            return MediaPlayerState.UNAVAILABLE

        output = self._output
        if output is None:
            return MediaPlayerState.UNAVAILABLE

        if output.receive_from is not None:
            # Could check signal status here if needed
            return MediaPlayerState.ON

        return MediaPlayerState.IDLE

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        output = self._output
        if output is None or output.receive_from is None:
            return None

        # Find the input port
        source_port = next(
            (inp for inp in self._inputs if inp.bay == output.receive_from),
            None,
        )

        if source_port:
            return source_port.name or f"Input {source_port.bay}"

        return None

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
                output_bay=self._output_bay,
            )
            # Request immediate coordinator refresh after state change
            await self.coordinator.async_request_refresh()
        except (Pulse8APIError, Pulse8ConnectionError) as err:
            _LOGGER.error("Error setting source for %s: %s", self.name, err)
