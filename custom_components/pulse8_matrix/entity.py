"""Base entity for Pulse8 Matrix."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Pulse8DataUpdateCoordinator


class Pulse8Entity(CoordinatorEntity[Pulse8DataUpdateCoordinator]):
    """Base entity for Pulse8 Matrix."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Pulse8DataUpdateCoordinator):
        """Initialize the entity."""
        super().__init__(coordinator)
        system = coordinator.data["system"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system.serial)},
            name=f"Pulse8 {system.model}",
            manufacturer="Pulse-Eight",
            model=system.model,
            sw_version=system.version,
        )


class Pulse8OutputEntity(Pulse8Entity):
    """Base entity for Pulse8 output ports."""

    def __init__(self, coordinator: Pulse8DataUpdateCoordinator, output):
        """Initialize the output entity."""
        super().__init__(coordinator)
        self._output_bay = output.bay
        self._attr_name = output.name

    def _get_current_output(self):
        """Get the current output port data."""
        for output in self.coordinator.data["outputs"]:
            if output.bay == self._output_bay:
                return output
        return None
