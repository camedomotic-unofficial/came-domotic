# CAME Domotic

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]
[![pre-commit][pre-commit-shield]][pre-commit]
[![Project Maintenance][maintenance-shield]][user_profile]

A [Home Assistant](https://www.home-assistant.io/) custom integration for [CAME](https://www.came.com/) Domotic home automation systems. It communicates locally with your CAME ETI/Domo server over your home network — no cloud connection required.

Built on top of the [aiocamedomotic](https://github.com/camedomotic-unofficial/aiocamedomotic) library.

## Supported features

| Platform          | Description                                                    |
| ----------------- | -------------------------------------------------------------- |
| **Light**         | On/off switches, dimmers, and RGB lights                       |
| **Cover**         | Shutters and motorized openings with tilt control              |
| **Climate**       | Thermoregulation zones (heating, cooling, fan speed)           |
| **Scene**         | Predefined scenarios                                           |
| **Switch**        | Relays and timers with timetable scheduling                    |
| **Binary sensor** | Digital inputs, server connectivity                            |
| **Sensor**        | Temperature, humidity, pressure, scenario status, ping latency |
| **Camera**        | TVCC/IP cameras with RTSP streaming and JPEG snapshots         |
| **Image**         | Floor plan map pages                                           |
| **Select**        | Plant-level thermoregulation season (Winter/Summer/Off)        |

The integration automatically discovers which device types are available based on your server's configuration. It uses a push-based update mechanism (long-polling) for near-instant state updates.

## Installation

### HACS (recommended)

This integration is not yet in the default HACS repository. You can install it as a **custom repository**:

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In the Home Assistant UI, go to **HACS** > **Integrations**.
3. Click the three-dot menu in the top right corner and select **Custom repositories**.
4. Enter the repository URL: `https://github.com/camedomotic-unofficial/came-domotic`
5. Select **Integration** as the category and click **Add**.
6. The integration will now appear in the HACS store. Click **Download** to install it.
7. Restart Home Assistant.

### Manual installation

1. Download the latest release from the [releases page][releases].
2. Extract (or copy) the `custom_components/came_domotic` folder into your Home Assistant `custom_components` directory.
3. Restart Home Assistant.

Your directory structure should look like this:

```text
config/
  custom_components/
    came_domotic/
      __init__.py
      manifest.json
      ...
```

## Setup

After installation and restart:

1. Go to **Settings** > **Devices & services**.
2. Click **Add integration** and search for **CAME Domotic**.
3. The integration will attempt to auto-discover a CAME server on your network. If found, you will only need to enter your credentials. Otherwise, enter the server's IP address (factory default: `192.168.1.3`) along with your username and password.

DHCP discovery is also supported — if a CAME device joins your network, Home Assistant will prompt you to set it up.

## Documentation

For full documentation including entity details, service actions, troubleshooting, and debug logging, see the [integration documentation](docs/came_domotic.markdown).

## Contributing

Contributions are welcome! Please read the [contribution guidelines](CONTRIBUTING.md) before getting started.

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/camedomotic-unofficial/came-domotic.svg?style=for-the-badge
[commits]: https://github.com/camedomotic-unofficial/came-domotic/commits/main
[license]: https://github.com/camedomotic-unofficial/came-domotic/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/camedomotic-unofficial/came-domotic.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40camedomotic--unofficial-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/camedomotic-unofficial/came-domotic.svg?style=for-the-badge
[releases]: https://github.com/camedomotic-unofficial/came-domotic/releases
[user_profile]: https://github.com/camedomotic-unofficial
