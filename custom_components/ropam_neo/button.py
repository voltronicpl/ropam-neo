"""Przyciski alarmu napadowego (PANIC) i pożarowego (FIRE)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import RopamNeoClient
from .const import CONF_FIRE_BUTTON, CONF_PANIC_BUTTON
from .entity import RopamEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    client: RopamNeoClient = entry.runtime_data
    entities: list[ButtonEntity] = []
    if entry.options.get(CONF_PANIC_BUTTON, True):
        entities.append(RopamPanicButton(entry, client))
    if entry.options.get(CONF_FIRE_BUTTON, True):
        entities.append(RopamFireButton(entry, client))
    async_add_entities(entities)


class RopamPanicButton(RopamEntity, ButtonEntity):
    _attr_name = "Alarm napadowy"
    _attr_icon = "mdi:alarm-light"

    def __init__(self, entry: ConfigEntry, client: RopamNeoClient) -> None:
        super().__init__(entry, client, "panic")

    async def async_press(self) -> None:
        await self._command(self._client.panic())


class RopamFireButton(RopamEntity, ButtonEntity):
    _attr_name = "Alarm pożarowy"
    _attr_icon = "mdi:fire-alert"

    def __init__(self, entry: ConfigEntry, client: RopamNeoClient) -> None:
        super().__init__(entry, client, "fire")

    async def async_press(self) -> None:
        await self._command(self._client.fire())
