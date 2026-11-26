"""Automatyczne uzbrajanie strefy 1, gdy wszystkie wybrane osoby wyjdą z domu."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import STATE_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

from .client import RopamNeoClient

ZONE_IDX = 0  # strefa 1
_UNSURE = (None, STATE_UNKNOWN, STATE_UNAVAILABLE)


class AutoArmWatcher:
    def __init__(
        self,
        hass: HomeAssistant,
        client: RopamNeoClient,
        persons: list[str],
        delay_seconds: float,
    ) -> None:
        self.hass = hass
        self.client = client
        self.persons = list(dict.fromkeys(persons))
        self.delay = max(0.0, float(delay_seconds))
        self._unsubs: list[Callable[[], None]] = []
        self._pending: CALLBACK_TYPE | None = None
        # uzbrajamy tylko po przejściu "ktoś w domu -> nikogo"
        self._ready = False

    # ----------------------------------------------------------------- stan

    def _states(self) -> list[str | None]:
        out = []
        for e in self.persons:
            s = self.hass.states.get(e)
            out.append(s.state if s is not None else None)
        return out

    def _someone_home(self) -> bool:
        return any(s == STATE_HOME for s in self._states())

    def _all_away(self) -> bool:
        states = self._states()
        return bool(states) and all(
            s not in _UNSURE and s != STATE_HOME for s in states
        )

    def _zone_armed(self) -> bool:
        st = self.client.state.status
        if st is None or len(st.zones) <= ZONE_IDX:
            return False
        z = st.zones[ZONE_IDX]
        return z.armed or z.night or z.exit_delay

    # ----------------------------------------------------------------- cykl

    @callback
    def start(self) -> None:
        self._ready = self._someone_home()
        if self.persons:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, self.persons, self._on_change
                )
            )
        mins = self.delay / 60
        self.client.log_info(
            f"Auto-uzbrajanie strefy 1: {len(self.persons)} os., opóźnienie "
            f"{mins:g} min, teraz {'ktoś w domu' if self._ready else 'nikogo/nie wiadomo'}"
        )

    @callback
    def stop(self) -> None:
        self._cancel(None)
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _cancel(self, reason: str | None) -> None:
        if self._pending is not None:
            self._pending()
            self._pending = None
            if reason:
                self.client.log_info(f"Auto-uzbrajanie anulowane: {reason}")

    # ----------------------------------------------------------------- zdarzenia

    @callback
    def _on_change(self, event: Event) -> None:
        if self._someone_home():
            self._cancel("ktoś wrócił do domu")
            self._ready = True
            return
        if not self._all_away():
            # ktoś ma status nieznany - nie ryzykujemy
            self._cancel("nieznana lokalizacja osoby")
            return
        if not self._ready or self._pending is not None:
            return
        if self.delay == 0:
            self._arm()
            return
        self.client.log_info(
            f"Nikogo w domu - uzbrojenie strefy 1 za {self.delay / 60:g} min"
        )
        self._pending = async_call_later(self.hass, self.delay, self._on_delay_end)

    @callback
    def _on_delay_end(self, _now: Any) -> None:
        self._pending = None
        if not self._all_away():
            self.client.log_info("Auto-uzbrajanie: ktoś wrócił w trakcie - bez uzbrajania")
            return
        self._arm()

    @callback
    def _arm(self) -> None:
        self._ready = False
        if self._zone_armed():
            self.client.log_info("Auto-uzbrajanie: strefa 1 już uzbrojona")
            return
        self.client.local_message("Nikogo w domu - uzbrajam strefę 1 (pełne)")
        self.hass.async_create_task(self._send())

    async def _send(self) -> None:
        try:
            await self.client.arm(1 << ZONE_IDX, night=False)
        except Exception as err:  # noqa: BLE001
            self.client.local_message(f"Auto-uzbrajanie nieudane: {err}")
