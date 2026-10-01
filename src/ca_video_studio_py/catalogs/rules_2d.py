from __future__ import annotations  # Enable forward references in type annotations

import json  # Parse the versioned rule catalog
from dataclasses import dataclass  # Store immutable catalog records
from importlib.resources import files  # Locate packaged catalog data


# Describes one built-in two-dimensional automaton rule
@dataclass(frozen=True)
class RuleCatalogEntry:
    key: str
    name: str
    category: str
    notation: str
    description: str
    recommendedInitial: str


# :: VOID -> (ruleCatalogEntry)
# Loads the packaged two-dimensional rule catalog in display order
def ruleCatalog() -> tuple[RuleCatalogEntry, ...]:
    resource = files("ca_video_studio_py.catalogs").joinpath("rules_2d.json")
    data = json.loads(resource.read_text(encoding="utf-8"))
    return tuple(
        RuleCatalogEntry(
            item["key"],
            item["name"],
            item["category"],
            item["notation"],
            item["description"],
            item["recommended_initial"],
        )
        for item in data
    )


# :: STRING -> ruleCatalogEntry
# Resolves a stable catalog key or reports the available choices
def getRule(key: str) -> RuleCatalogEntry:
    for entry in ruleCatalog():
        if entry.key == key:
            return entry
    choices = ", ".join(entry.key for entry in ruleCatalog())
    raise KeyError(f"unknown 2D rule preset {key!r}; expected one of {choices}")
