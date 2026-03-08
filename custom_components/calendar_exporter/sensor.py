from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_FEED_NAME

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Calendar Exporter URL sensor."""
    # Grab the relative URL we saved in __init__.py
    relative_url = hass.data[DOMAIN][entry.entry_id]
    
    # Add the sensor to Home Assistant
    async_add_entities([CalendarExportUrlSensor(hass, entry, relative_url)])


class CalendarExportUrlSensor(SensorEntity):
    """Representation of a Sensor that holds the secret URL."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, relative_url: str):
        """Initialize the sensor."""
        self.hass = hass
        self.entry = entry
        self._relative_url = relative_url
        
        # Give it a nice name and icon in the UI
        feed_name = entry.data.get(CONF_FEED_NAME, entry.title)
        self._attr_name = f"{feed_name} Export Link"
        self._attr_unique_id = f"{entry.entry_id}_sensor"
        self._attr_icon = "mdi:calendar-link"

    @property
    def state(self):
        """The state of the sensor."""
        return "Active"

    @property
    def extra_state_attributes(self):
        """Return the actual URLs as attributes so they can be easily copied."""
        base_url = self.hass.config.external_url or self.hass.config.internal_url or ""
        return {
            "absolute_url": f"{base_url}{self._relative_url}",
            "relative_url": self._relative_url,
            "merged_calendars": self.entry.data.get("calendars", [])
        }
