"""Formularz konfiguracji Ropam Neo."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import LoginInfo, NeoError, RopamNeoClient
from .const import (
    CONF_AUTO_DELAY,
    CONF_AUTO_PERSONS,
    CONF_DEVICE_ID,
    CONF_FIRE_BUTTON,
    CONF_PANIC_BUTTON,
    CONF_TCP_KEY,
    CONF_USER_CODE,
    CONF_Z1_ACTION,
    CONF_Z1_DELAY,
    CONF_Z1_SENSORS,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): TextSelector(),
            vol.Required(
                CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_DEVICE_ID, default=defaults.get(CONF_DEVICE_ID, "")
            ): TextSelector(),
            vol.Required(CONF_TCP_KEY, default=defaults.get(CONF_TCP_KEY, "")): _PASSWORD,
            vol.Required(
                CONF_USER_CODE, default=defaults.get(CONF_USER_CODE, "")
            ): _PASSWORD,
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_HOST: str(user_input[CONF_HOST]).strip(),
        CONF_PORT: int(user_input[CONF_PORT]),
        CONF_DEVICE_ID: str(user_input[CONF_DEVICE_ID]).strip(),
        CONF_TCP_KEY: str(user_input[CONF_TCP_KEY]).strip(),
        CONF_USER_CODE: str(user_input[CONF_USER_CODE]).strip(),
    }


async def _validate(data: dict[str, Any]) -> tuple[LoginInfo | None, str | None]:
    if not data[CONF_DEVICE_ID]:
        return None, "missing_device_id"
    if not data[CONF_TCP_KEY]:
        return None, "missing_tcp_key"
    if not data[CONF_USER_CODE]:
        return None, "missing_user_code"
    client = RopamNeoClient(
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_DEVICE_ID],
        data[CONF_TCP_KEY],
        data[CONF_USER_CODE],
    )
    try:
        return await client.async_test(), None
    except NeoError as err:
        _LOGGER.debug("Test połączenia nieudany: %s", err)
        return None, err.code
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Nieoczekiwany błąd testu połączenia")
        return None, "unknown"


class RopamNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        defaults: dict[str, Any] = {}
        if user_input is not None:
            data = _clean(user_input)
            defaults = data
            await self.async_set_unique_id(data[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            _, error = await _validate(data)
            if error is None:
                return self.async_create_entry(
                    title=f"Ropam Neo ({data[CONF_HOST]})", data=data
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=_schema(defaults), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return RopamNeoOptionsFlow()


class RopamNeoOptionsFlow(OptionsFlow):
    """Zmiana danych połączenia bez usuwania integracji."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        defaults = dict(self.config_entry.data)
        panic = self.config_entry.options.get(CONF_PANIC_BUTTON, True)
        fire = self.config_entry.options.get(CONF_FIRE_BUTTON, True)
        opts = self.config_entry.options
        z1_sensors = list(opts.get(CONF_Z1_SENSORS) or [])
        z1_delay = int(opts.get(CONF_Z1_DELAY, 0))
        z1_action = opts.get(CONF_Z1_ACTION, "panic")
        auto_persons = list(opts.get(CONF_AUTO_PERSONS) or [])
        auto_delay = int(opts.get(CONF_AUTO_DELAY, 5))
        if user_input is not None:
            data = _clean(user_input)
            panic = bool(user_input.get(CONF_PANIC_BUTTON, True))
            fire = bool(user_input.get(CONF_FIRE_BUTTON, True))
            z1_sensors = list(user_input.get(CONF_Z1_SENSORS) or [])
            z1_delay = int(user_input.get(CONF_Z1_DELAY, 0))
            z1_action = user_input.get(CONF_Z1_ACTION, "panic")
            auto_persons = list(user_input.get(CONF_AUTO_PERSONS) or [])
            auto_delay = int(user_input.get(CONF_AUTO_DELAY, 5))
            defaults = data
            changed = any(
                data[k] != self.config_entry.data.get(k)
                for k in (CONF_HOST, CONF_PORT, CONF_DEVICE_ID, CONF_TCP_KEY, CONF_USER_CODE)
            )
            # test połączenia tylko gdy zmieniły się dane połączenia
            error = (await _validate(data))[1] if changed else None
            if error is None:
                if changed:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=data,
                        title=f"Ropam Neo ({data[CONF_HOST]})",
                    )
                return self.async_create_entry(
                    data={
                        CONF_PANIC_BUTTON: panic,
                        CONF_FIRE_BUTTON: fire,
                        CONF_Z1_SENSORS: z1_sensors,
                        CONF_Z1_DELAY: z1_delay,
                        CONF_Z1_ACTION: z1_action,
                        CONF_AUTO_PERSONS: auto_persons,
                        CONF_AUTO_DELAY: auto_delay,
                    }
                )
            errors["base"] = error
        schema = _schema(defaults).extend(
            {
                vol.Required(CONF_PANIC_BUTTON, default=panic): BooleanSelector(),
                vol.Required(CONF_FIRE_BUTTON, default=fire): BooleanSelector(),
                vol.Optional(CONF_Z1_SENSORS, default=z1_sensors): EntitySelector(
                    EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Required(CONF_Z1_DELAY, default=z1_delay): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=600,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(CONF_Z1_ACTION, default=z1_action): SelectSelector(
                    SelectSelectorConfig(
                        options=["panic", "fire"],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="zone_action",
                    )
                ),
                vol.Optional(CONF_AUTO_PERSONS, default=auto_persons): EntitySelector(
                    EntitySelectorConfig(domain="person", multiple=True)
                ),
                vol.Required(CONF_AUTO_DELAY, default=auto_delay): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=120,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
