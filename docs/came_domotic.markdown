---
title: CAME Domotic
description: Instructions on how to integrate CAME Domotic devices with Home Assistant.
ha_category:
  - Cover
  - Climate
  - Light
  - Scene
  - Select
  - Sensor
  - Switch
  - Camera
  - Binary sensor
  - Image
ha_release: "2025.3"
ha_iot_class: Local Push
ha_codeowners:
  - "@camedomotic-unofficial"
ha_domain: came_domotic
ha_platforms:
  - binary_sensor
  - camera
  - climate
  - cover
  - image
  - light
  - scene
  - select
  - sensor
  - switch
ha_integration_type: hub
ha_config_flow: true
ha_dhcp: true
ha_quality_scale: bronze
---

The **CAME Domotic** {% term integration %} allows you to control and monitor your [CAME](https://www.came.com/) Domotic home automation system from Home Assistant. CAME is an Italian manufacturer known for gate automation, access control, and smart home systems.

This integration communicates locally with your CAME ETI/Domo server over your home network using the [aiocamedomotic](https://github.com/camedomotic-unofficial/aiocamedomotic) library. No cloud connection is required.

## Supported devices

The integration works with CAME Domotic servers (ETI/Domo system). The following device types are supported:

- **Lights** - On/off switches, dimmers, and RGB lights
- **Covers** - Shutters and other motorized openings with tilt control
- **Climate** - Thermoregulation zones with heating/cooling and fan speed control
- **Scenes** - Predefined scenarios that can be activated
- **Switches** - Relays (on/off control) and timers (enable/disable with scheduling)
- **Binary sensors** - Digital inputs and server connectivity status
- **Sensors** - Temperature, humidity, pressure sensors and scenario status
- **Cameras** - TVCC/IP cameras with RTSP streaming and JPEG snapshots
- **Images** - Floor plan map pages from the CAME server
- **Select** - Plant-level thermoregulation season (Winter/Summer/Off)

{% note %}
Which device types are available depends on the features configured on your specific CAME server. The integration automatically discovers and creates {% term entities %} only for the features your server reports.
{% endnote %}

## Prerequisites

Before setting up the integration, make sure you have:

- A CAME Domotic ETI/Domo server connected to your local network
- Network access from your Home Assistant instance to the CAME server (factory-default IP addresses are `192.168.1.3` and `192.168.0.3`)
- Valid credentials for the CAME server (factory defaults are username `admin` and password `admin`)

{% important %}
It is strongly recommended to change the default credentials on your CAME server before setting up this integration.
{% endimportant %}

{% include integrations/config_flow.md %}

The integration supports three ways to discover your CAME server:

1. **Automatic discovery**: When you start the setup flow, the integration probes known factory-default IP addresses and your local subnet for a CAME server. If found, it skips the host field and asks only for credentials.
2. **DHCP discovery**: If a CAME device (identified by its MAC address prefix `00:1C:B2`) joins your network, Home Assistant will notify you automatically.
3. **Manual setup**: Enter the server's IP address and credentials yourself.

### Configuration parameters

{% configuration_basic %}
Host:
description: "The IP address of your CAME Domotic server."
Username:
description: "The username for authenticating with the CAME server."
Password:
description: "The password for authenticating with the CAME server."
{% endconfiguration_basic %}

## Supported functionality

### Lights

The integration exposes CAME lights as Home Assistant light {% term entities %}. Three light types are supported:

| Light type | Color mode | Features                                     |
| ---------- | ---------- | -------------------------------------------- |
| Step/Step  | On/Off     | Turn on, turn off                            |
| Dimmer     | Brightness | Turn on, turn off, set brightness (0-100%)   |
| RGB        | RGB        | Turn on, turn off, set brightness, set color |

State changes use optimistic updates for a responsive UI: the entity state updates immediately after sending a command, then syncs with the server's confirmed state when the next long-poll update arrives.

### Covers

CAME openings (shutters) are exposed as cover entities. Supported operations:

- **Open** / **Close** / **Stop** - Motor control
- **Open tilt** / **Close tilt** / **Stop tilt** - Slat control

{% note %}
Position tracking is not available. The CAME server only reports motor direction (opening, closing, stopped), not a numerical position.
{% endnote %}

### Climate

Thermoregulation zones are exposed as climate entities. The CAME system uses a two-axis model:

- **Season** (plant-level): Winter or Summer, controlled via the **Thermo season** select entity
- **Mode** (zone-level): Off, Manual, Auto, or Jolly

The season determines whether the zone operates in heating or cooling mode:

| Season | Manual mode | Auto mode | Off |
| ------ | ----------- | --------- | --- |
| Winter | Heat        | Auto      | Off |
| Summer | Cool        | Auto      | Off |

Additional climate features:

- **Target temperature**: 5.0-34.0 &deg;C in 0.1 &deg;C steps
- **Fan mode**: Off, Low, Medium, High, Auto (only for fan-coil zones)
- **Preset**: Jolly mode (a special CAME scheduling preset)

{% tip %}
When you manually adjust the target temperature, the zone automatically switches to Manual mode. This is because the CAME server ignores temperature changes in Auto or Jolly modes.
{% endtip %}

### Scenes

CAME scenarios are exposed as scene entities. Activating a scene triggers the corresponding scenario on the CAME server. A companion sensor entity reports each scenario's status (Off, Triggered, Active) and tracks when it was last triggered.

### Switches

Two types of switches are available:

- **Relays**: Simple on/off control for generic relay actuators
- **Timers**: Enable/disable control for scheduled timers, with extra state attributes showing the configured schedule (active days and time slots)

Timer switches also support the **set_timer_timetable** entity service for configuring schedules from automations (see [Actions](#actions) below).

### Binary sensors

- **Digital inputs**: Read-only sensors that report Active or Idle state, with a `last_triggered` timestamp attribute
- **Server connectivity**: A diagnostic sensor that shows whether the CAME server is reachable

### Sensors

| Sensor type      | Device class                       | Unit           | Description                                                          |
| ---------------- | ---------------------------------- | -------------- | -------------------------------------------------------------------- |
| Zone temperature | Temperature                        | &deg;C         | Current temperature from thermoregulation zones                      |
| Analog sensor    | Temperature, Humidity, or Pressure | &deg;C, %, hPa | Standalone analog sensors                                            |
| Analog input     | Temperature, Humidity, or Pressure | &deg;C, %, hPa | Analog input probes                                                  |
| Scenario status  | -                                  | -              | Reports Off, Triggered, or Active                                    |
| Ping latency     | Duration                           | ms             | Round-trip time to the CAME server (diagnostic, disabled by default) |

### Cameras

IP cameras connected to the CAME Domotic system are exposed as camera entities. Features depend on the camera configuration:

- **RTSP streaming**: Live video stream via the HA stream component (for cameras with RTSP URIs)
- **JPEG snapshots**: Still image capture from cameras with a snapshot URI

{% note %}
Flash-based (SWF) cameras are not supported for streaming.
{% endnote %}

### Images

Floor plan map pages configured on the CAME server are displayed as image entities. These show the background images (floor plans) from the server's map configuration.

### Select

A **Thermo season** select entity is created when thermoregulation zones are present. It controls the plant-level season setting that applies to all zones:

- **Winter** - Zones operate in heating mode
- **Summer** - Zones operate in cooling mode
- **Plant off** - All thermoregulation is disabled

## Area and floor mapping

On first setup, the integration reads the plant topology (floors and rooms) from the CAME server and automatically creates matching floors and areas in Home Assistant. Device entities are assigned to the corresponding area based on their room configuration on the CAME server.

## Device information

Each CAME server appears as a device in Home Assistant with the following information:

- **Manufacturer**: CAME
- **Model**: Server type and board information as reported by the server
- **Serial number**: Server serial number (when available)
- **Software version**: Server firmware version
- **Hardware version**: Server board identifier

Individual device entities (lights, covers, climate zones, etc.) appear as child devices linked to the server.

## Data updates

The integration uses a **push-based** update mechanism:

1. On startup, a full data fetch retrieves all device states from the server.
2. A background **long-polling** task continuously listens for incremental state changes. When the server reports a change, the affected entities update immediately.
3. A separate **ping coordinator** monitors server connectivity every 60 seconds (every 10 seconds when disconnected).

This means state changes made through the CAME system (physical buttons, other clients) are reflected in Home Assistant within seconds, without waiting for a polling interval.

If the server becomes unreachable, all entities are marked as unavailable. When connectivity is restored, a full data refresh is performed and the long-poll loop resumes automatically.

## Actions

The integration provides the following service actions:

### Action `came_domotic.force_refresh`

Force a full data refresh from the CAME server. Useful after making configuration changes directly on the server.

| Data attribute    | Required | Description                         |
| ----------------- | -------- | ----------------------------------- |
| `config_entry_id` | Yes      | The CAME Domotic server to refresh. |

### Action `came_domotic.create_user`

Create a new user on the CAME Domotic server.

| Data attribute    | Required | Description                                                                                                       |
| ----------------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `config_entry_id` | Yes      | The CAME Domotic server.                                                                                          |
| `username`        | Yes      | Username for the new user.                                                                                        |
| `password`        | Yes      | Password for the new user.                                                                                        |
| `group`           | No       | Terminal group name. Defaults to `*` (all groups). Use the `get_terminal_groups` action to list available groups. |

### Action `came_domotic.delete_user`

Delete a user from the CAME Domotic server.

| Data attribute    | Required | Description                     |
| ----------------- | -------- | ------------------------------- |
| `config_entry_id` | Yes      | The CAME Domotic server.        |
| `username`        | Yes      | Username of the user to delete. |

{% note %}
You cannot delete the user that the integration is currently authenticated with.
{% endnote %}

### Action `came_domotic.change_password`

Change a user's password on the CAME Domotic server. If you change the password of the currently authenticated user, the integration's stored credentials are updated automatically.

| Data attribute     | Required | Description                        |
| ------------------ | -------- | ---------------------------------- |
| `config_entry_id`  | Yes      | The CAME Domotic server.           |
| `username`         | Yes      | Username whose password to change. |
| `current_password` | Yes      | The user's current password.       |
| `new_password`     | Yes      | The desired new password.          |

### Action `came_domotic.get_users`

List all users configured on the CAME Domotic server. This action returns a response with the list of usernames.

| Data attribute    | Required | Description                       |
| ----------------- | -------- | --------------------------------- |
| `config_entry_id` | Yes      | The CAME Domotic server to query. |

### Action `came_domotic.get_terminal_groups`

List available terminal groups on the CAME Domotic server. Call this before creating a user to discover valid group names.

| Data attribute    | Required | Description                       |
| ----------------- | -------- | --------------------------------- |
| `config_entry_id` | Yes      | The CAME Domotic server to query. |

### Action `came_domotic.set_timer_timetable`

Configure the schedule for a CAME Domotic timer switch, including active days and time slots. This is an entity service targeting timer switch entities.

| Data attribute | Required | Description                                                                                                                                        |
| -------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `days`         | No       | List of day names the timer should be active (e.g., `["monday", "wednesday", "friday"]`). Days not listed will be disabled.                        |
| `slots`        | No       | List of up to 4 time slot objects with `start` and optional `stop` times in `HH:MM` or `HH:MM:SS` format. Slots beyond those provided are cleared. |

#### Example: Set a timer schedule

```yaml
action: came_domotic.set_timer_timetable
target:
  entity_id: switch.my_timer
data:
  days:
    - monday
    - tuesday
    - wednesday
    - thursday
    - friday
  slots:
    - start: "08:00"
      stop: "12:00"
    - start: "14:00"
      stop: "18:00"
```

## Known limitations

- **Cover position**: The CAME API does not report cover position as a percentage. Only the motor direction (opening, closing, stopped) is available.
- **Camera support**: The TVCC camera feature is not advertised in the server's feature list and is fetched best-effort. Flash (SWF) cameras are not supported for streaming.
- **Thermoregulation temperature in Auto/Jolly mode**: The CAME server silently ignores temperature changes when a zone is in Auto or Jolly mode. The integration switches to Manual mode when you set a temperature to ensure the change takes effect.

## Troubleshooting

### Cannot connect to the CAME server

- Verify that the CAME server is powered on and connected to your network.
- Check that the IP address is correct. The factory default is `192.168.1.3` or `192.168.0.3`.
- Ensure there are no firewall rules blocking communication between Home Assistant and the CAME server.
- Try accessing the server's web interface directly in a browser at `http://<server-ip>/index.html` to confirm it is reachable.

### Authentication failed

- Double-check the username and password.
- If you recently changed the password on the CAME server, use the **Reconfigure** option in {% my integrations title="**Settings** > **Devices & services**" %} to update the stored credentials.
- The integration will automatically prompt for re-authentication if credentials become invalid.

### Entities show as unavailable

- The integration marks all entities as unavailable when the CAME server cannot be reached.
- Check network connectivity and server status. Try accessing the server's web interface directly in a browser at `http://<server-ip>/index.html` to confirm it is up and running.
- The ping coordinator checks every 60 seconds (10 seconds when disconnected). Entities will become available again automatically when connectivity is restored.

### Devices or entities are missing

- Only device types that your CAME server reports as available will be discovered. Check your server's configuration to ensure the expected features are enabled.
- Use the **Force refresh** action (`came_domotic.force_refresh`) to trigger a full re-scan of all devices.
- If you added devices to the CAME system after the integration was set up, the long-poll mechanism will detect plant configuration changes and refresh automatically.

### State changes are not reflected

- State changes from the CAME server are delivered via long-polling and typically appear within less than 1 second, but could take a bit more.
- If updates seem stuck, try the **Force refresh** action to perform a full data sync.

### Enabling debug logs

To help diagnose issues, you can enable debug logging for the integration. Add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.came_domotic: debug
    aiocamedomotic: debug
    aiocamedomotic.traffic: debug
```

- `custom_components.came_domotic` enables debug logs for the integration itself (coordinator activity, entity setup, service calls).
- `aiocamedomotic` enables debug logs for the underlying library (API calls, connection lifecycle).
- `aiocamedomotic.traffic` can be used instead of (or in addition to) `aiocamedomotic` to log the raw HTTP requests and responses exchanged with the CAME server, which is useful for diagnosing protocol-level issues.

{% tip %}
All log output is automatically anonymized by the library. Sensitive information such as passwords, usernames, keycodes, and MAC addresses is never included in log messages. You can safely share debug logs when reporting issues.
{% endtip %}

### Reporting issues

If you are experiencing issues that are not covered above, please [open an issue](https://github.com/camedomotic-unofficial/came-domotic/issues) on the project's GitHub repository. Include relevant debug log entries and a description of your setup to help with troubleshooting.

## Removing the integration

This integration follows standard integration removal. No extra steps are required.

{% include integrations/remove_device_service.md %}
