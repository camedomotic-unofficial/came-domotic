"""Data models for CAME Domotic."""

from __future__ import annotations

from dataclasses import dataclass, field

from aiocamedomotic.models import (
    AnalogIn,
    AnalogSensor,
    Camera,
    DigitalInput,
    Light,
    MapPage,
    Opening,
    PlantTopology,
    Relay,
    Scenario,
    ServerInfo,
    ThermoZone,
    Timer,
)


@dataclass
class PingResult:
    """Result of a server ping operation."""

    connected: bool
    latency_ms: float | None


@dataclass
class CameDomoticServerData:
    """Holds all device data fetched from the CAME server.

    Device lists contain the actual library model objects.
    The coordinator stores an instance of this class and mutates
    the objects in-place when incremental updates arrive.
    """

    server_info: ServerInfo | None = None
    thermo_zones: dict[int, ThermoZone] = field(default_factory=dict)
    scenarios: dict[int, Scenario] = field(default_factory=dict)
    openings: dict[int, Opening] = field(default_factory=dict)
    lights: dict[int, Light] = field(default_factory=dict)
    digital_inputs: dict[int, DigitalInput] = field(default_factory=dict)
    analog_sensors: dict[int, AnalogSensor] = field(default_factory=dict)
    analog_inputs: dict[int, AnalogIn] = field(default_factory=dict)
    relays: dict[int, Relay] = field(default_factory=dict)
    timers: dict[int, Timer] = field(default_factory=dict)
    cameras: dict[int, Camera] = field(default_factory=dict)
    maps: dict[int, MapPage] = field(default_factory=dict)
    topology: PlantTopology | None = None
