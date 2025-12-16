"""DataUpdateCoordinator for Pulse8 Matrix."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pulse_eight_matrix_client import PulseEightMatrixClient, Pulse8ConnectionError, Pulse8APIError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Pulse8DataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Pulse8 Matrix data."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, poll_interval: int):
        """Initialize coordinator."""
        self.client = PulseEightMatrixClient(host=host, port=port)
        self.system_details = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )

    async def _async_update_data(self):
        """Fetch data from the matrix."""
        try:
            if not self.client._session:
                await self.client.connect()

            # Get system details on first run
            if self.system_details is None:
                self.system_details = await self.client.get_system_details()

            # Get current port states
            ports = await self.client.get_ports()

            return {
                "ports": ports,
                "inputs": [p for p in ports if p.mode == "Input"],
                "outputs": [p for p in ports if p.mode == "Output"],
                "system": self.system_details,
            }
        except (Pulse8ConnectionError, Pulse8APIError) as err:
            raise UpdateFailed(f"Error communicating with matrix: {err}") from err

    async def async_shutdown(self):
        """Cleanup on shutdown."""
        await self.client.close()