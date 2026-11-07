"""Switch platform for Solakon ONE integration.

The switches write 0/1 registers from the FoxESS register map that the
Solakon ONE Modbus protocol lists but that are not verified on every firmware.
They are disabled by default; an unsupported register shows as unknown.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REGISTERS
from .entity import SolakonEntity
from .types import SolakonConfigEntry

_LOGGER = logging.getLogger(__name__)

SWITCH_ENTITY_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="buzzer",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    SwitchEntityDescription(
        key="idle_state",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: SolakonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solakon ONE switch entities."""
    device_info = await config_entry.runtime_data.hub.async_get_device_info()

    async_add_entities(
        (
            SolakonSwitch(config_entry, device_info, description)
            for description in SWITCH_ENTITY_DESCRIPTIONS
            if description.key in REGISTERS
            and REGISTERS[description.key].get("rw", False)
        ),
        True,
    )


class SolakonSwitch(SolakonEntity, SwitchEntity):
    """A 0/1 register of the Solakon ONE as switch."""

    def __init__(
        self,
        config_entry: SolakonConfigEntry,
        device_info: dict,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(config_entry, device_info, description.key)
        self._register_config = REGISTERS[description.key]
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = (self.coordinator.data or {}).get(self.entity_description.key)
        if value in (0, 1):
            self._attr_is_on = value == 1
        else:
            if value is not None:
                _LOGGER.warning(
                    "Unexpected value %s for %s", value, self.entity_description.key
                )
            self._attr_is_on = None
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_write(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_write(0)

    async def _async_write(self, value: int) -> None:
        address = self._register_config["address"]
        _LOGGER.info(
            "Setting %s at address %d to %d",
            self.entity_description.key,
            address,
            value,
        )
        success = await self._config_entry.runtime_data.hub.async_write_register(
            address, value
        )
        if not success:
            _LOGGER.error("Failed to set %s to %d", self.entity_description.key, value)
            return
        self._attr_is_on = value == 1
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
