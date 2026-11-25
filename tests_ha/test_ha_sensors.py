"""Czujniki HA wpięte w strefę 1."""
import asyncio
from unittest.mock import patch

from homeassistant.const import CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

import sim_central as S
from test_init import DATA
from custom_components.ropam_neo.const import (
    CONF_Z1_ACTION,
    CONF_Z1_DELAY,
    CONF_Z1_SENSORS,
    DOMAIN,
)

OKNO = "binary_sensor.okno_salon"
DRZWI = "binary_sensor.drzwi_wejsciowe"


async def _setup(hass, delay=0, action="panic"):
    hass.states.async_set(OKNO, "off", {"friendly_name": "Okno salon"})
    hass.states.async_set(DRZWI, "off", {"friendly_name": "Drzwi"})
    central = S.Central()
    server = await asyncio.start_server(
        lambda r, w: S.handle(r, w, central), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**DATA, CONF_PORT: port},
        unique_id=S.DEVICE_ID,
        options={CONF_Z1_SENSORS: [OKNO, DRZWI], CONF_Z1_DELAY: delay, CONF_Z1_ACTION: action},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.ropam_neo.async_register_panel"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    zone = next(
        s.entity_id for s in hass.states.async_all() if s.entity_id.startswith("alarm_control_panel.")
    )
    return central, server, entry, zone


async def _wait(hass, cond, n=40):
    for _ in range(n):
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()
        if cond():
            return True
    return cond()


async def _arm(hass, zone, service):
    await hass.services.async_call("alarm_control_panel", service, {"entity_id": zone}, blocking=True)


def _sent(central, t):
    return sum(1 for ft, _ in central.received if ft == t)


async def _teardown(hass, entry, server):
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    server.close()


async def test_open_when_armed_full_triggers(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass)
    hass.states.async_set(OKNO, "on")  # rozbrojona -> nic
    await hass.async_block_till_done()
    hass.states.async_set(OKNO, "off")
    await _arm(hass, zone, "alarm_arm_away")
    assert await _wait(hass, lambda: hass.states.get(zone).state == "armed_away")
    hass.states.async_set(OKNO, "on")
    assert await _wait(hass, lambda: _sent(central, 42) == 1)
    # drugi czujnik w tym samym cyklu nie dubluje alarmu
    hass.states.async_set(DRZWI, "on")
    await _wait(hass, lambda: False, n=6)
    assert _sent(central, 42) == 1
    await _teardown(hass, entry, server)


async def test_night_arm_ignored(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass)
    await _arm(hass, zone, "alarm_arm_night")
    assert await _wait(hass, lambda: hass.states.get(zone).state == "armed_night")
    hass.states.async_set(OKNO, "on")
    await _wait(hass, lambda: False, n=8)
    assert _sent(central, 42) == 0
    await _teardown(hass, entry, server)


async def test_delay_cancelled_by_disarm(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass, delay=1, action="fire")
    await _arm(hass, zone, "alarm_arm_away")
    assert await _wait(hass, lambda: hass.states.get(zone).state == "armed_away")
    hass.states.async_set(DRZWI, "on")
    await hass.async_block_till_done()
    await _arm(hass, zone, "alarm_disarm")
    assert await _wait(hass, lambda: hass.states.get(zone).state == "disarmed")
    await asyncio.sleep(1.3)
    await hass.async_block_till_done()
    assert _sent(central, 43) == 0
    await _teardown(hass, entry, server)


async def test_delay_expires_fires(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass, delay=1, action="fire")
    await _arm(hass, zone, "alarm_arm_away")
    assert await _wait(hass, lambda: hass.states.get(zone).state == "armed_away")
    hass.states.async_set(DRZWI, "on")
    await hass.async_block_till_done()
    assert hass.states.get(zone).attributes["czujniki_ha_otwarte"] == [DRZWI]
    await asyncio.sleep(1.3)
    assert await _wait(hass, lambda: _sent(central, 43) == 1)
    await _teardown(hass, entry, server)


async def test_arm_with_open_sensor_warns(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass)
    hass.states.async_set(OKNO, "on")
    await hass.async_block_till_done()
    await _arm(hass, zone, "alarm_arm_away")
    assert await _wait(hass, lambda: hass.states.get(zone).state == "armed_away")
    msg = next(s for s in hass.states.async_all() if s.entity_id.endswith("ostatni_komunikat"))
    assert "otwartych czujnikach" in msg.state
    assert _sent(central, 42) == 0
    await _teardown(hass, entry, server)
