"""Config flow for EGYM."""

import probatio as vol
import requests

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import CONF_BASE_URL, CONF_ECCENTRIC_FACTOR, CONF_ORDER, DEFAULT_ECCENTRIC_FACTOR, DOMAIN
from .egym_api import Api, AuthenticationError, DiscoveryError, EgymError

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_NAME, default=""): str,
        vol.Optional(CONF_BASE_URL, default=""): str,
        vol.Optional(CONF_ORDER, default=""): TextSelector(TextSelectorConfig(multiline=True)),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ORDER, default=""): TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(CONF_ECCENTRIC_FACTOR, default=DEFAULT_ECCENTRIC_FACTOR): NumberSelector(
            NumberSelectorConfig(min=1, max=3, step=0.01, mode=NumberSelectorMode.BOX)
        ),
    }
)


def _check_login(email, password, base_url):
    api = Api(email=email, password=password, base_url=base_url or None)
    found = api.base_url
    api.logout()
    return found


class EgymConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "EgymOptionsFlow":
        return EgymOptionsFlow()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            base_url = user_input.get(CONF_BASE_URL, "").strip().rstrip("/")
            name = user_input.get(CONF_NAME, "").strip() or email.split("@")[0]
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            try:
                base_url = await self.hass.async_add_executor_job(
                    _check_login, email, user_input[CONF_PASSWORD], base_url
                )
            except DiscoveryError:
                errors[CONF_BASE_URL] = "discovery_failed"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (EgymError, requests.RequestException):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_NAME: name,
                        CONF_BASE_URL: base_url,
                    },
                    options={CONF_ORDER: user_input.get(CONF_ORDER, "").strip()},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input),
            errors=errors,
            description_placeholders={"example_url": "https://yourgym.netpulse.com"},
        )


class EgymOptionsFlow(OptionsFlowWithReload):
    """Change the machine order; the entry reloads so names follow."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={
                CONF_ORDER: user_input.get(CONF_ORDER, "").strip(),
                CONF_ECCENTRIC_FACTOR: float(user_input.get(CONF_ECCENTRIC_FACTOR, DEFAULT_ECCENTRIC_FACTOR)),
            })
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, self.config_entry.options),
        )
