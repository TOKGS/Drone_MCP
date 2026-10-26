"""The 4.6 variant pin set is data, not code, and must not drift from the default one.

`sources-4.6.yaml` exists because a fleet on 4.6 firmware gets wrong answers from the 4.7 pin:
ARMING_CHECK is declared only in 4.6, ATC_ACCEL_* are renamed in 4.7. These checks are cheap and
catch the two realistic failures: a library glob added to sources.yaml but not to the variant, and
a tag in the yaml that no longer matches the tarball pin in research/tags-4.6.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return yaml.safe_load((REPO / name).read_text(encoding="utf-8"))


def _sources(conf: dict) -> dict[str, dict]:
    return {source["id"]: source for source in conf["sources"]}


def test_variant_differs_only_in_the_ardupilot_pin_and_its_paths() -> None:
    main, variant = _load("sources.yaml"), _load("sources-4.6.yaml")
    assert variant["corpus_root"].startswith("data/4.6/")
    assert variant["licenses_dir"].startswith("data/4.6/")
    by_id_main, by_id_variant = _sources(main), _sources(variant)
    assert list(by_id_variant) == list(by_id_main)
    for source_id, source in by_id_main.items():
        if source_id == "ardupilot":
            continue
        assert by_id_variant[source_id] == source, f"{source_id} drifted from sources.yaml"
    assert by_id_variant["ardupilot"]["ref"] != by_id_main["ardupilot"]["ref"]


def test_variant_pin_is_a_4_6_tag_and_not_a_branch() -> None:
    ardupilot = _sources(_load("sources-4.6.yaml"))["ardupilot"]
    assert ardupilot["ref_kind"] == "tag"
    assert re.fullmatch(r"Copter-4\.6\.\d+", ardupilot["ref"]), ardupilot["ref"]
    assert ardupilot["version_label"] == ardupilot["ref"]


def test_variant_tarball_pins_match_the_yaml() -> None:
    variant = _load("sources-4.6.yaml")
    tags = json.loads((REPO / "research" / "tags-4.6.json").read_text(encoding="utf-8"))
    for source_id, source in _sources(variant).items():
        if source_id not in tags["sources"]:
            continue
        assert tags["sources"][source_id]["ref"] == source["ref"], source_id
        assert tags["sources"][source_id]["tarball"].endswith(f"/{source['ref']}")


def test_arm_sources_env_selects_the_variant(monkeypatch) -> None:
    from ardupilot_research_mcp import config

    monkeypatch.setenv("ARM_SOURCES", str(REPO / "sources-4.6.yaml"))
    assert config.sources_path() == REPO / "sources-4.6.yaml"
