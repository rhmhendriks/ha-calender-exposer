# Home Assistant Calendar Exposer

Export your internal Home Assistant calendars as a live, secure `.ics` feed to use in Outlook, Google Calendar, or Apple Calendar.

## Features
* **Merge Calendars:** Select one or multiple Home Assistant calendars to combine into a single feed.
* **Multiple Feeds:** Create as many independent feeds as you need directly from the UI.
* **Secure by Default:** Uses a randomly generated UUID for the URL, acting as a secure token so your schedules remain private.
* **Easy Access:** Automatically creates a sensor in Home Assistant that holds your secret URL for easy copy-pasting.

## Installation

### Method 1: HACS (Recommended)
1. Open HACS in Home Assistant.
2. Go to **Integrations** -> Click the three dots in the top right -> **Custom repositories**.
3. Add `https://github.com/rhmhendriks/ha-calender-exposer` with the category **Integration**.
4. Click **Download** and restart Home Assistant.

### Method 2: Manual
1. Download the `custom_components/calendar_exporter` folder from this repository.
2. Place it inside your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration
1. Go to **Settings** -> **Devices & Services** -> **Add Integration**.
2. Search for **Calendar Exporter**.
3. Give your feed a name and select the calendars you want to export.
4. Once added, click on the Integration to view its entities.
5. Click on the newly created **Sensor entity** and look at the "Attributes" to find your `absolute_url`.
6. Copy that URL and paste it into Outlook, Gmail, or Apple Calendar!
