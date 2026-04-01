"""Tests to verify all 18 cobalt entities have complete dossiers."""
from __future__ import annotations

import pytest
from src.analysis.mineral_supply_chains import get_mineral_by_name


@pytest.fixture
def cobalt():
    return get_mineral_by_name("Cobalt")


class TestAllMinesHaveDossiers:
    def test_cobalt_has_mines(self, cobalt):
        assert cobalt is not None
        assert "mines" in cobalt
        assert len(cobalt["mines"]) == 9

    @pytest.mark.parametrize("mine_name", [
        "Tenke Fungurume (TFM)",
        "Kisanfu (KFM)",
        "Kamoto (KCC)",
        "Mutanda",
        "Murrin Murrin",
        "Moa JV",
        "Voisey's Bay",
        "Sudbury Basin",
        "Raglan Mine",
    ])
    def test_mine_has_dossier(self, cobalt, mine_name):
        mine = next((m for m in cobalt["mines"] if m["name"] == mine_name), None)
        assert mine is not None, f"Mine '{mine_name}' not found"
        assert "dossier" in mine, f"Mine '{mine_name}' missing dossier"

    @pytest.mark.parametrize("mine_name", [
        "Tenke Fungurume (TFM)",
        "Kisanfu (KFM)",
        "Kamoto (KCC)",
        "Mutanda",
        "Murrin Murrin",
        "Moa JV",
        "Voisey's Bay",
        "Sudbury Basin",
        "Raglan Mine",
    ])
    def test_mine_dossier_has_required_fields(self, cobalt, mine_name):
        mine = next(m for m in cobalt["mines"] if m["name"] == mine_name)
        d = mine["dossier"]
        assert "z_score" in d
        assert "credit_trend" in d
        assert "ubo_chain" in d
        assert isinstance(d["ubo_chain"], list)
        assert len(d["ubo_chain"]) >= 2
        assert "recent_intel" in d
        assert isinstance(d["recent_intel"], list)


class TestAllRefineriesHaveDossiers:
    def test_cobalt_has_refineries(self, cobalt):
        assert "refineries" in cobalt
        assert len(cobalt["refineries"]) == 9

    @pytest.mark.parametrize("refinery_name", [
        "Huayou Cobalt",
        "GEM Co.",
        "Jinchuan Group",
        "Umicore Kokkola",
        "Umicore Hoboken",
        "Fort Saskatchewan",
        "Long Harbour NPP",
        "Niihama Nickel Refinery",
        "Harjavalta",
    ])
    def test_refinery_has_dossier(self, cobalt, refinery_name):
        ref = next((r for r in cobalt["refineries"] if r["name"] == refinery_name), None)
        assert ref is not None, f"Refinery '{refinery_name}' not found"
        assert "dossier" in ref, f"Refinery '{refinery_name}' missing dossier"

    @pytest.mark.parametrize("refinery_name", [
        "Huayou Cobalt",
        "GEM Co.",
        "Jinchuan Group",
        "Umicore Kokkola",
        "Umicore Hoboken",
        "Fort Saskatchewan",
        "Long Harbour NPP",
        "Niihama Nickel Refinery",
        "Harjavalta",
    ])
    def test_refinery_dossier_has_required_fields(self, cobalt, refinery_name):
        ref = next(r for r in cobalt["refineries"] if r["name"] == refinery_name)
        d = ref["dossier"]
        assert "z_score" in d
        assert "credit_trend" in d
        assert "ubo_chain" in d
        assert isinstance(d["ubo_chain"], list)
        assert len(d["ubo_chain"]) >= 2
        assert "recent_intel" in d


class TestFOCIScoresInRange:
    def test_all_foci_scores_valid(self, cobalt):
        for entity_list in [cobalt["mines"], cobalt["refineries"]]:
            for entity in entity_list:
                if "dossier" in entity and "foci_score" in entity["dossier"]:
                    score = entity["dossier"]["foci_score"]
                    assert 0 <= score <= 100, f"{entity['name']} FOCI score {score} out of range"

    def test_critical_foci_entities(self, cobalt):
        """Jinchuan, Harjavalta, Huayou should have FOCI >= 88."""
        critical_names = ["Jinchuan Group", "Harjavalta", "Huayou Cobalt"]
        for entity_list in [cobalt["mines"], cobalt["refineries"]]:
            for entity in entity_list:
                if entity["name"] in critical_names and "dossier" in entity:
                    assert entity["dossier"].get("foci_score", 0) >= 88, \
                        f"{entity['name']} should have critical FOCI score"

    def test_allied_entities_low_foci(self, cobalt):
        """Voisey's Bay, Long Harbour, Umicore should have FOCI <= 30."""
        allied_names = ["Voisey's Bay", "Long Harbour NPP", "Umicore Kokkola", "Umicore Hoboken"]
        for entity_list in [cobalt["mines"], cobalt["refineries"]]:
            for entity in entity_list:
                if entity["name"] in allied_names and "dossier" in entity:
                    assert entity["dossier"].get("foci_score", 100) <= 30, \
                        f"{entity['name']} should have low FOCI score"
