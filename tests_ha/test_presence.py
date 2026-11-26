"""Auto-uzbrajanie strefy 1 po wyjściu wszystkich osób."""
import asyncio
from unittest.mock import patch

from homeassistant.const import CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

import sim_central as S
from test_init import DATA
from custom_components.ropam_neo.const import CONF_AUTO_DELAY, CONF_AUTO_PERSONS, DOMAIN

A = "person.damian"
B = "person.druga_osoba"


async def _setup(hass, a="home", b="home", delay=0):
    hass.states.async_set(A, a)
    hass.states.async_set(B, b)
    central = S.Central()
    server = await asyncio.start_server(lambda r, w: S.handle(r, w, central), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    entry = MockConfigEntry(
        domain=DOMAIN, data={**DATA, CONF_PORT: port}, unique_id=S.DEVICE_ID,
        options={CONF_AUTO_PERSONS: [A, B], CONF_AUTO_DELAY: delay},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.ropam_neo.async_register_panel"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    zone = next(s.entity_id for s in hass.states.async_all() if s.entity_id.startswith("alarm_control_panel."))
    return central, server, entry, zone


async def _settle(hass, n=8):
    for _ in range(n):
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()


def _arms(central):
    return [d for t, d in central.received if t == 7]


async def _teardown(hass, entry, server):
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    server.close()


async def test_all_leave_arms_full(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass)
    hass.states.async_set(A, "not_home")
    await _settle(hass)
    assert _arms(central) == []  # druga osoba w domu
    hass.states.async_set(B, "Praca")  # inna strefa = poza domem
    await _settle(hass)
    assert len(_arms(central)) == 1 and _arms(central)[0][:2] == bytes([1, 0])
    assert hass.states.get(zone).state == "armed_away"
    await _teardown(hass, entry, server)


async def test_no_arm_on_startup_when_away(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass, "not_home", "not_home")
    hass.states.async_set(A, "Praca")
    await _settle(hass)
    assert _arms(central) == []
    await _teardown(hass, entry, server)


async def test_unknown_location_blocks(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass)
    hass.states.async_set(A, "unavailable")
    hass.states.async_set(B, "not_home")
    await _settle(hass)
    assert _arms(central) == []
    await _teardown(hass, entry, server)


async def test_no_rearm_after_remote_disarm(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass)
    hass.states.async_set(A, "not_home")
    hass.states.async_set(B, "not_home")
    await _settle(hass)
    assert len(_arms(central)) == 1
    await hass.services.async_call("alarm_control_panel", "alarm_disarm", {"entity_id": zone}, blocking=True)
    await _settle(hass)
    hass.states.async_set(A, "Sklep")
    await _settle(hass)
    assert len(_arms(central)) == 1
    # ktoś wraca i znowu wszyscy wychodzą -> ponowne uzbrojenie
    hass.states.async_set(A, "home")
    await _settle(hass)
    hass.states.async_set(A, "not_home")
    await _settle(hass)
    assert len(_arms(central)) == 2
    await _teardown(hass, entry, server)


async def test_delay_and_return_cancels(hass, no_frontend, socket_enabled):
    central, server, entry, zone = await _setup(hass, delay=0.02)  # 1,2 s
    hass.states.async_set(A, "not_home")
    hass.states.async_set(B, "not_home")
    await _settle(hass, 4)
    hass.states.async_set(B, "home")
    await asyncio.sleep(1.4)
    await _settle(hass)
    assert _arms(central) == []
    hass.states.async_set(B, "not_home")
    await asyncio.sleep(1.4)
    await _settle(hass)
    assert len(_arms(central)) == 1
    await _teardown(hass, entry, server)
