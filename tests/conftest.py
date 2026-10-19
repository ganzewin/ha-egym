"""Make Home Assistant's test config find the integration in this repository."""

import pathlib

import custom_components  # the test config's package from pytest-homeassistant-custom-component

pytest_plugins = ["pytest_homeassistant_custom_component"]

_REPO_COMPONENTS = str(pathlib.Path(__file__).parent.parent / "custom_components")
if _REPO_COMPONENTS not in custom_components.__path__:
    custom_components.__path__.append(_REPO_COMPONENTS)
