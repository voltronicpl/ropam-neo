"""Czujniki z Home Assistant wpięte w strefę 1 centrali.

Otwarcie czujnika przy PEŁNYM uzbrojeniu strefy 1 (nie nocnym) wywołuje
po opóźnieniu alarm w centrali (napad albo pożar). Rozbrojenie anuluje.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

from .client import RopamNeoClient

ACTION_PANIC = "panic"
ACTION_FIRE = "fire"
ACTION_NAMES = {ACTION_PANIC: "alarm napadowy", ACTION_FIRE: "alarm pożarowy"}
ZONE_IDX = 0  # strefa 1


class ZoneSensorWatcher:
    def __init__(
        self,
        hass: HomeAssistant,
        client: RopamNeoClient,
        sensors: list[str],
        delay: int,
        action: str,
    ) -> None:
        self.hass = hass
        self.client = client
        self.sensors = list(dict.fromkeys(sensors))
        self.delay = max(0, int(delay))
        self.action = action if action in ACTION_NAMES else ACTION_PANIC
        self._unsubs: list[Callable[[], None]] = []
        self._pending: CALLBACK_TYPE | None = None
        self._pending_sensor: str | None = None
        self._was_armed = False
        self._triggered = False

    # ----------------------------------------------------------------- stan

    def _armed_full(self) -> bool:
        st = self.client.state.status
        if st is None or len(st.zones) <= ZONE_IDX:
            return False
        z = st.zones[ZONE_IDX]
        return z.armed and not z.night and not z.exit_delay

    def _name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        if state is not None and state.name:
            return f"{state.name} ({entity_id})"
        return entity_id

    def open_sensors(self) -> list[str]:
        return [
            e
            for e in self.sensors
            if (s := self.hass.states.get(e)) is not None and s.state == STATE_ON
        ]

    # ----------------------------------------------------------------- cykl

    @callback
    def start(self) -> None:
        self._was_armed = self._armed_full()
        self._publish()
        if self.sensors:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, self.sensors, self._on_sensor_change
                )
            )
        self._unsubs.append(self.client.add_listener(self._on_client_update))
        self.client.log_info(
            f"Czujniki HA strefy 1: {len(self.sensors)} szt., opóźnienie "
            f"{self.delay} s, reakcja: {ACTION_NAMES[self.action]}"
        )

    @callback
    def stop(self) -> None:
        self._cancel(None)
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self.client.ha_open_sensors = []

    def _publish(self) -> None:
        self.client.ha_open_sensors = self.open_sensors()

    @callback
    def _cancel(self, reason: str | None) -> None:
        if self._pending is not None:
            self._pending()
            self._pending = None
            if reason:
                self.client.log_info(
                    f"Czujniki HA: anulowano alarm ({reason})"
                )
        self._pending_sensor = None

    # ----------------------------------------------------------------- zdarzenia

    @callback
    def _on_client_update(self) -> None:
        armed = self._armed_full()
        was = self._was_armed
        # zapis przed akcjami - local_message woła listenerów ponownie
        self._was_armed = armed
        if armed and not was:
            self._triggered = False
            opened = self.open_sensors()
            if opened:
                names = ", ".join(self._name(e) for e in opened)
                self.client.local_message(
                    f"Strefa 1 uzbrojona przy otwartych czujnikach HA: {names}"
                )
        elif not armed and was:
            self._cancel("strefa 1 rozbrojona")
            self._triggered = False

    @callback
    def _on_sensor_change(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        entity_id = event.data.get("entity_id")
        self._publish()
        self.client.notify()
        if new is None or new.state != STATE_ON:
            return
        if old is None or old.state != "off":
            # pomijamy przejścia z unavailable/unknown (restart, zanik zasięgu)
            return
        if not self._armed_full():
            return
        if self._triggered or self._pending is not None:
            return
        name = self._name(entity_id)
        if self.delay == 0:
            self.client.log_info(f"Czujnik HA {name} otwarty przy uzbrojonej strefie 1")
            self._fire(name)
            return
        self.client.log_info(
            f"Czujnik HA {name} otwarty przy uzbrojonej strefie 1 - "
            f"alarm za {self.delay} s, jeśli nie rozbroisz"
        )
        self._pending_sensor = name
        self._pending = async_call_later(self.hass, self.delay, self._on_delay_end)

    @callback
    def _on_delay_end(self, _now: Any) -> None:
        self._pending = None
        name = self._pending_sensor or "?"
        self._pending_sensor = None
        if not self._armed_full():
            self.client.log_info("Czujniki HA: strefa 1 rozbrojona w czasie - bez alarmu")
            return
        self._fire(name)

    @callback
    def _fire(self, name: str) -> None:
        self._triggered = True
        self.client.local_message(
            f"Czujnik HA {name}: wywołuję {ACTION_NAMES[self.action]}"
        )
        coro = self.client.panic() if self.action == ACTION_PANIC else self.client.fire()
        self.hass.async_create_task(self._send(coro))

    async def _send(self, coro) -> None:
        try:
            await coro
        except Exception as err:  # noqa: BLE001
            self.client.log_error(f"Czujniki HA: nie udało się wysłać alarmu: {err}")
