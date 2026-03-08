import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_CALENDARS, CONF_FEED_NAME


class CalendarExporterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Calendar Exporter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_FEED_NAME],
                data=user_input,
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_FEED_NAME, default="My Exported Calendar"): str,
                vol.Required(CONF_CALENDARS): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="calendar",
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
