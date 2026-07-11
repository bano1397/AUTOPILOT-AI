"""Plugin discovery.

Walks the configured plugin packages and imports every submodule so that the
registration decorators execute. Packages that do not yet exist are skipped
(the platform is built incrementally); import errors *inside* an existing plugin
module propagate so problems fail fast.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable

from app.core.logging import get_logger

logger = get_logger("app.registry.scanner")

# Packages scanned for plugins. They are created over the course of the roadmap;
# absent packages are silently skipped.
DEFAULT_PLUGIN_PACKAGES: tuple[str, ...] = (
    "app.infrastructure",
    "app.tools",
    "app.agents",
    "app.workflows",
    "app.integrations",
)


def discover_plugins(packages: Iterable[str] = DEFAULT_PLUGIN_PACKAGES) -> int:
    """Import all submodules of the given packages. Returns the module count imported."""
    imported = 0
    for package_name in packages:
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError as exc:
            if exc.name == package_name:
                logger.debug("plugin_package_absent", extra={"package": package_name})
                continue
            raise  # a real missing dependency inside the package — fail fast

        package_path = getattr(package, "__path__", None)
        if package_path is None:
            continue  # module, not a package

        for module_info in pkgutil.walk_packages(package_path, prefix=f"{package_name}."):
            importlib.import_module(module_info.name)
            imported += 1

    logger.info("plugins_discovered", extra={"modules_imported": imported})
    return imported
