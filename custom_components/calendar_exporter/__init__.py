import logging
from datetime import timedelta
import icalendar
from dateutil import parser

from aiohttp import web
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.http import HomeAssistantView
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_CALENDARS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Calendar Exporter from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register the HTTP View for this specific config entry
    view = CalendarExportView(hass, entry)
    hass.http.register_view(view)
    
    # Store the URL path for the sensor to pick up
    hass.data[DOMAIN][entry.entry_id] = view.url

    # Register a service to get the feed URL manually
    async def get_feed_url(call: ServiceCall):
        base_url = hass.config.external_url or hass.config.internal_url
        url = f"{base_url}{view.url}"
        _LOGGER.info(f"Calendar Exporter URL for {entry.title}: {url}")
        return {"url": url}

    hass.services.async_register(
        DOMAIN, "get_feed_url", get_feed_url, supports_response=True
    )

    # Forward the setup to sensor.py so it creates your UI entity
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the sensor entity cleanly
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok


class CalendarExportView(HomeAssistantView):
    """View to retrieve the iCal feed."""

    requires_auth = False # Allows Outlook/Gmail to read it without a HA token

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the view."""
        self.hass = hass
        self.entry = entry
        # Secure URL using the randomly generated entry_id
        self.url = f"/api/calendar_exporter/{entry.entry_id}.ics"
        self.name = f"calendar_exporter_{entry.entry_id}"

    async def get(self, request: web.Request) -> web.Response:
        """Handle the GET request for the ical feed."""
        calendars = self.entry.data.get(CONF_CALENDARS, [])
        
        # Look back 30 days and look forward 365 days
        start = dt_util.now() - timedelta(days=30)
        end = dt_util.now() + timedelta(days=365)

        cal = icalendar.Calendar()
        cal.add('prodid', f'-//Home Assistant Calendar Exporter//')
        cal.add('version', '2.0')
        cal.add('x-wr-calname', self.entry.title)

        for entity_id in calendars:
            try:
                # Use standard HA service to get events
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": entity_id,
                        "start_date_time": start.isoformat(),
                        "end_date_time": end.isoformat(),
                    },
                    blocking=True,
                    return_response=True,
                )

                events = response.get(entity_id, {}).get("events", [])
                
                for evt in events:
                    ical_evt = icalendar.Event()
                    ical_evt.add('summary', evt.get('summary', 'Unknown'))
                    
                    if 'start' in evt:
                        ical_evt.add('dtstart', parser.parse(evt['start']))
                    if 'end' in evt:
                        ical_evt.add('dtend', parser.parse(evt['end']))
                    if 'description' in evt:
                        ical_evt.add('description', evt['description'])
                    if 'location' in evt:
                        ical_evt.add('location', evt['location'])
                    
                    cal.add_component(ical_evt)

            except Exception as e:
                _LOGGER.error("Error fetching events for %s: %s", entity_id, e)

        return web.Response(
            body=cal.to_ical(), 
            content_type="text/calendar",
            charset="utf-8"
        )
