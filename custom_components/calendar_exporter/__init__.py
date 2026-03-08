import logging
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
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


def _parse_event_datetime(value):
    """Parse Home Assistant calendar values to date/datetime for ICS fields."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return value

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        # Date-only values represent all-day events.
        if "T" not in value:
            return date.fromisoformat(value)
        parsed = parser.isoparse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return parsed

    if isinstance(value, dict):
        if "date" in value:
            return date.fromisoformat(value["date"])
        if "dateTime" in value:
            parsed = parser.isoparse(value["dateTime"])
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return parsed

    raise ValueError(f"Unsupported event datetime value: {value!r}")


def _build_event_uid(entity_id: str, event: dict) -> str:
    """Build a stable UID for calendar clients to track updates reliably."""
    if event.get("uid"):
        return str(event["uid"])

    identity = "|".join(
        [
            entity_id,
            str(event.get("summary", "")),
            str(event.get("start", "")),
            str(event.get("end", "")),
            str(event.get("description", "")),
            str(event.get("location", "")),
        ]
    )
    digest = hashlib.sha1(identity.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"{digest}@{DOMAIN}"


def _as_utc_datetime(value) -> datetime:
    """Convert date/datetime values to timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return value.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    raise ValueError(f"Cannot convert to UTC datetime: {value!r}")

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
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', self.entry.title)
        cal.add('x-published-ttl', 'PT15M')
        cal.add('x-wr-timezone', str(dt_util.DEFAULT_TIME_ZONE))

        feed_last_modified = datetime(1970, 1, 1, tzinfo=timezone.utc)

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

                entity_response = response.get(entity_id, {}) if isinstance(response, dict) else {}
                if isinstance(entity_response, dict) and "events" in entity_response:
                    events = entity_response.get("events", [])
                elif isinstance(entity_response, list):
                    events = entity_response
                elif isinstance(response, dict) and "events" in response:
                    events = response.get("events", [])
                else:
                    events = []
                
                for evt in events:
                    try:
                        ical_evt = icalendar.Event()
                        ical_evt.add('summary', evt.get('summary', 'Unknown'))

                        start_value = _parse_event_datetime(evt.get('start'))
                        end_value = _parse_event_datetime(evt.get('end'))
                        if start_value is None:
                            _LOGGER.debug("Skipping event without start for %s: %s", entity_id, evt)
                            continue

                        modified_source = (
                            evt.get('updated')
                            or evt.get('last_modified')
                            or evt.get('created')
                            or start_value
                        )
                        modified_value = _parse_event_datetime(modified_source)
                        modified_at = _as_utc_datetime(modified_value)

                        ical_evt.add('uid', _build_event_uid(entity_id, evt))
                        ical_evt.add('dtstamp', modified_at)
                        ical_evt.add('last-modified', modified_at)
                        ical_evt.add('dtstart', start_value)

                        if end_value is not None:
                            ical_evt.add('dtend', end_value)
                        if 'description' in evt and evt['description']:
                            ical_evt.add('description', evt['description'])
                        if 'location' in evt and evt['location']:
                            ical_evt.add('location', evt['location'])

                        cal.add_component(ical_evt)
                        if modified_at > feed_last_modified:
                            feed_last_modified = modified_at
                    except Exception as err:
                        # Keep exporting remaining events when one event has invalid data.
                        _LOGGER.warning("Skipping invalid event for %s: %s", entity_id, err)

            except Exception as e:
                _LOGGER.error("Error fetching events for %s: %s", entity_id, e)

        if feed_last_modified.year == 1970:
            feed_last_modified = datetime.now(timezone.utc)

        body = cal.to_ical()
        etag = hashlib.sha256(body).hexdigest()
        quoted_etag = f'"{etag}"'

        if request.headers.get("If-None-Match") == quoted_etag:
            return web.Response(
                status=304,
                headers={
                    "ETag": quoted_etag,
                    "Cache-Control": "public, max-age=300, must-revalidate",
                    "Last-Modified": format_datetime(feed_last_modified, usegmt=True),
                },
            )

        return web.Response(
            body=body,
            content_type="text/calendar",
            charset="utf-8",
            headers={
                "ETag": quoted_etag,
                "Cache-Control": "public, max-age=300, must-revalidate",
                "Last-Modified": format_datetime(feed_last_modified, usegmt=True),
            },
        )
