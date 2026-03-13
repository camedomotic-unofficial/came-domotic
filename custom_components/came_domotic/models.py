"""Data models for CAME Domotic."""

from __future__ import annotations

from dataclasses import dataclass, field

from aiocamedomotic.models import (
    DigitalInput,
    Floor,
    Light,
    Opening,
    Room,
    Scenario,
    ServerInfo,
    ThermoZone,
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
    floors: dict[int, Floor] = field(default_factory=dict)
    rooms: dict[int, Room] = field(default_factory=dict)
