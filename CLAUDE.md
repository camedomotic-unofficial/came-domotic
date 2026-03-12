# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Home Assistant custom integration for CAME Domotic devices. Distributed via HACS (Home Assistant Community Store). Built from the `integration_blueprint` / cookiecutter template.

- **Domain**: `came_domotic`
- **IoT class**: `local_push` — communicates with a local CAME Domotic server via long polling
- **Multiple config entries**: supports multiple instances (e.g., different local devices)
- **API layer**: `api.py` is a wrapper around the `aiocamedomotic` library (not direct HTTP calls).
- **aiocamedomotic docs**: Fetch the up-to-date API reference from these remote URLs:
  - Overview: `https://raw.githubusercontent.com/camedomotic-unofficial/aiocamedomotic/refs/heads/main/llms.txt`
  - Full reference: `https://raw.githubusercontent.com/camedomotic-unofficial/aiocamedomotic/refs/heads/main/llms-full.txt`
    Always consult these when working with `aiocamedomotic` usage in `api.py` or anywhere else in the integration.

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
pytest --durations=10 --cov-report term-missing --cov=custom_components.came_domotic tests
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

Uses **ruff** (formatter + linter), **mypy** (type checking), **bandit** (security), **codespell** (spelling), and **prettier** (JSON/YAML). Configured in `pyproject.toml` and `.pre-commit-config.yaml`.

## Architecture

### Integration entry point flow

1. User configures via UI (`config_flow.py` -> `CameDomoticFlowHandler`)
2. `__init__.py:async_setup_entry` creates the API client and coordinator, stores them in `entry.runtime_data`
3. Coordinator performs an initial full fetch (`_async_update_data()`), then a background long-poll task (`_async_long_poll_loop()`) receives incremental updates from the server and pushes them to entities via `async_set_updated_data()`
4. Platforms (`binary_sensor.py`, `sensor.py`, `switch.py`) register entities that read from `coordinator.data`

### Key modules (`custom_components/came_domotic/`)

- **api.py** - Client wrapping the `aiocamedomotic` library to talk to the local CAME Domotic server. Custom exception hierarchy: `ApiClientError` -> `CommunicationError` / `AuthenticationError`. Includes `async_get_updates()` for long-polling.
- **coordinator.py** - Push-based `DataUpdateCoordinator` subclass (no `update_interval`). `_async_update_data()` for initial/full fetch, `_async_long_poll_loop()` for incremental updates via background task. Merges partial updates via `zone.raw_data.update(update.raw_data)`. Translates API errors to `ConfigEntryAuthFailed` / `UpdateFailed`.
- **entity.py** - Base `CoordinatorEntity` subclass setting common attributes (attribution, device info, unique_id)
- **config_flow.py** - Setup flow (user step, DHCP discovery, reconfigure, reauth)
- **const.py** - Domain name, defaults, long-poll constants (`DEFAULT_LONG_POLL_TIMEOUT`, `RECONNECT_DELAY`, `UPDATE_THROTTLE_DELAY`)

### Adding a new device type platform

Pattern for adding future platforms (e.g., lights, openings):

1. Add `async_get_<device_type>()` method to `api.py` (same exception-translation pattern)
2. Include it in `api.async_get_data()` for initial fetch
3. Handle `DeviceType.<TYPE>` in `coordinator._merge_updates()` using `device.raw_data.update(update.raw_data)`
4. Create platform file (e.g., `light.py`) with entities reading from `coordinator.data["<key>"]`
5. Add platform to `PLATFORMS` list in `__init__.py`

### Type alias

`CameDomoticConfigEntry = ConfigEntry[RuntimeData]` — used throughout for typed access to `entry.runtime_data.coordinator`.

### Testing patterns

- Tests use `pytest-homeassistant-custom-component` which provides HA test fixtures
- `conftest.py` defines shared fixtures: `bypass_get_data` (mocks API success), `error_on_get_data` (simulates comm error), `auth_error_on_get_data` (simulates auth error)
- `asyncio_mode = auto` in `setup.cfg` — all async tests run automatically without `@pytest.mark.asyncio`
- Config entries in tests are created via `MockConfigEntry` from the HA test helpers

## Logging

- Every module with meaningful logic has `_LOGGER = logging.getLogger(__name__)` (except `api.py` which uses `__package__` to log under the integration domain)
- **DEBUG**: routine operations (connection attempts, data fetches, entity setup, coordinator init)
- **INFO**: significant lifecycle events (setup complete, unload complete, config entry created/updated)
- **WARNING**: recoverable issues (auth failures, missing zones, unload failures)
- Never log credentials (passwords, usernames). Only log host addresses for connection context.
- Avoid double-logging errors that are caught and re-raised — log before re-raising only when the context would otherwise be lost

## CI & Merge Workflow

The `main` branch is protected by a GitHub ruleset. All four CI checks must pass before a PR can merge:

- **Pre-commit** — ruff, mypy, bandit, codespell, prettier
- **HACS** — HACS store validation
- **Hassfest** — Home Assistant integration validation (manifest, translations, config flow)
- **Run tests** — pytest with 100% coverage requirement

These run on every PR and push to `main` (defined in `.github/workflows/tests.yaml`). Always run `pre-commit run --all-files` and `pytest` locally before pushing to catch issues early.

## Code Style

- **ruff** formatter with 88-char line length
- **ruff** isort rules configured in `pyproject.toml` with `force_sort_within_sections`, known first party: `custom_components.came_domotic, tests`
- `from __future__ import annotations` in all Python files
