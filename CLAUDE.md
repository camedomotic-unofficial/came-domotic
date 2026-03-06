# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Home Assistant custom integration for CAME Domotic devices. Distributed via HACS (Home Assistant Community Store). Built from the `integration_blueprint` / cookiecutter template.

- **Domain**: `came_domotic_unofficial`
- **IoT class**: local polling — communicates with a local CAME Domotic server
- **Single config entry**: only one instance allowed
- **API layer**: `api.py` is a wrapper around the `aiocamedomotic` library (not direct HTTP calls). The current placeholder code will be replaced with `aiocamedomotic` calls.
- **aiocamedomotic docs**: `examples/aiocamedomotic-quickreference.md` (overview) and `examples/aiocamedomotic-fullreference.md` (detailed API). Always consult these files when working with `aiocamedomotic` usage in `api.py` or anywhere else in the integration.

## Commands

### Run all tests

```bash
pytest --timeout=9 --durations=10 -p no:sugar tests
```

### Run a single test file or test

```bash
pytest tests/test_api.py
pytest tests/test_api.py::test_function_name
```

### Run tests with coverage report (as configured in setup.cfg)

```bash
pytest --durations=10 --cov-report term-missing --cov=custom_components.came_domotic_unofficial tests
```

Coverage is configured to fail under 100% (`setup.cfg [coverage:report]`).

### Install dependencies

```bash
pip install -r requirements_test.txt
```

### Linting (pre-commit)

```bash
pre-commit run --all-files
```

Uses **black** (formatter), **flake8** (linter), **reorder-python-imports**, and **prettier** (JSON/YAML).

## Architecture

### Integration entry point flow

1. User configures via UI (`config_flow.py` -> `CameDomoticUnofficialFlowHandler`)
2. `__init__.py:async_setup_entry` creates the API client and coordinator, stores them in `entry.runtime_data`
3. Coordinator polls the local CAME server via `aiocamedomotic` on a timer and distributes data to entities
4. Platforms (`binary_sensor.py`, `sensor.py`, `switch.py`) register entities that read from `coordinator.data`

### Key modules (`custom_components/came_domotic_unofficial/`)

- **api.py** - Client wrapping the `aiocamedomotic` library to talk to the local CAME Domotic server. Custom exception hierarchy: `ApiClientError` -> `CommunicationError` / `AuthenticationError`
- **coordinator.py** - `DataUpdateCoordinator` subclass. Translates API auth errors into `ConfigEntryAuthFailed` and other errors into `UpdateFailed`
- **entity.py** - Base `CoordinatorEntity` subclass setting common attributes (attribution, device info, unique_id)
- **config_flow.py** - Setup flow (user step + reconfigure) and options flow (configurable scan interval, min 10s, default 30s)
- **const.py** - Domain name, defaults, icons

### Type alias

`CameDomoticUnofficialConfigEntry = ConfigEntry[RuntimeData]` — used throughout for typed access to `entry.runtime_data.coordinator`.

### Testing patterns

- Tests use `pytest-homeassistant-custom-component` which provides HA test fixtures
- `conftest.py` defines shared fixtures: `bypass_get_data` (mocks API success), `error_on_get_data` (simulates comm error), `auth_error_on_get_data` (simulates auth error)
- `asyncio_mode = auto` in `setup.cfg` — all async tests run automatically without `@pytest.mark.asyncio`
- Config entries in tests are created via `MockConfigEntry` from the HA test helpers

## Code Style

- **black** with 88-char line length
- **isort** configured in `setup.cfg` with `force_sort_within_sections`, known first party: `custom_components.came_domotic_unofficial, tests`
- `from __future__ import annotations` in all Python files
