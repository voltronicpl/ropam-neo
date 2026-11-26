"""Integracja Ropam Neo (NeoLTE-IP / NeoGSM-IP / Neo-IP) dla Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import RopamNeoClient
from .const import (
    CONF_AUTO_DELAY,
    CONF_AUTO_PERSONS,
    CONF_DEVICE_ID,
    CONF_TCP_KEY,
    CONF_USER_CODE,
    CONF_Z1_ACTION,
    CONF_Z1_DELAY,
    CONF_Z1_SENSORS,
    DEFAULT_PORT,
    DOMAIN,
    EVENT_MESSAGE,
    PLATFORMS,
    SETUP_TIMEOUT,
)
from .presence import AutoArmWatcher
from .ha_sensors import ACTION_PANIC, ZoneSensorWatcher
from .panel import async_register_panel, async_unregister_panel, clients

_LOGGER = logging.getLogger(__name__)

type RopamConfigEntry = ConfigEntry[RopamNeoClient]


async def async_setup_entry(hass: HomeAssistant, entry: RopamConfigEntry) -> bool:
    data = entry.data
    client = RopamNeoClient(
        host=data[CONF_HOST],
        port=int(data.get(CONF_PORT, DEFAULT_PORT)),
        device_id=data[CONF_DEVICE_ID],
        tcp_key=data[CONF_TCP_KEY],
        user_code=data[CONF_USER_CODE],
    )
    # zakładka diagnostyki dostępna także, gdy połączenie się nie udaje
    clients(hass)[entry.entry_id] = client
    await async_register_panel(hass)

    client.start()
    if not await client.wait_ready(SETUP_TIMEOUT):
        if client.state.status is None:
            reason = client.state.last_error or "brak statusu z centrali"
            await client.stop()
            raise ConfigEntryNotReady(f"Ropam Neo: {reason}")
        _LOGGER.warning(
            "Ropam Neo: brak konfiguracji z centrali - używam nazw domyślnych"
        )

    def _on_message(text: str) -> None:
        hass.bus.async_fire(
            EVENT_MESSAGE, {"entry_id": entry.entry_id, "message": text}
        )

    entry.async_on_unload(client.add_message_listener(_on_message))
    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    sensors = entry.options.get(CONF_Z1_SENSORS) or []
    if sensors:
        watcher = ZoneSensorWatcher(
            hass,
            client,
            sensors,
            int(entry.options.get(CONF_Z1_DELAY, 0)),
            entry.options.get(CONF_Z1_ACTION, ACTION_PANIC),
        )
        watcher.start()
        entry.async_on_unload(watcher.stop)

    persons = entry.options.get(CONF_AUTO_PERSONS) or []
    if persons:
        auto = AutoArmWatcher(
            hass, client, persons, float(entry.options.get(CONF_AUTO_DELAY, 5)) * 60
        )
        auto.start()
        entry.async_on_unload(auto.stop)
    return True


async def _async_reload(hass: HomeAssistant, entry: RopamConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RopamConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        client = clients(hass).get(entry.entry_id)
        if client is not None:
            await client.stop()
    return ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    clients(hass).pop(entry.entry_id, None)
    if not hass.config_entries.async_entries(DOMAIN) or all(
        e.entry_id == entry.entry_id for e in hass.config_entries.async_entries(DOMAIN)
    ):
        async_unregister_panel(hass)
