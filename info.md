[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

A Home Assistant custom integration for [CAME](https://www.came.com/) Domotic home automation systems. Communicates locally with your CAME ETI/Domo server — no cloud connection required.

## Supported features

- **Lights** - On/off, dimmers, and RGB
- **Covers** - Shutters with tilt control
- **Climate** - Thermoregulation zones (heating, cooling, fan speed)
- **Scenes** - Predefined scenarios
- **Switches** - Relays and timers with scheduling
- **Sensors** - Temperature, humidity, pressure, digital inputs, connectivity
- **Cameras** - RTSP streaming and JPEG snapshots
- **Images** - Floor plan map pages

The integration auto-discovers available device types and uses push-based updates (long-polling) for near-instant state synchronization.

{% if not installed %}

## Installation

1. In HACS, go to **Integrations** and click the three-dot menu > **Custom repositories**.
2. Add `https://github.com/camedomotic-unofficial/came-domotic` as an **Integration**.
3. Click **Download**, then restart Home Assistant.

{% endif %}

## Setup

1. Go to **Settings** > **Devices & services** > **Add integration**.
2. Search for **CAME Domotic**.
3. Enter your server's IP address and credentials.

For full documentation, see the [integration docs](https://github.com/camedomotic-unofficial/came-domotic/blob/main/docs/came_domotic.markdown).

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/camedomotic-unofficial/came-domotic.svg?style=for-the-badge
[commits]: https://github.com/camedomotic-unofficial/came-domotic/commits/main
[license]: https://github.com/camedomotic-unofficial/came-domotic/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/camedomotic-unofficial/came-domotic.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/camedomotic-unofficial/came-domotic.svg?style=for-the-badge
[releases]: https://github.com/camedomotic-unofficial/came-domotic/releases
