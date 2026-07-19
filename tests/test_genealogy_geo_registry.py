from crewai_custom_tools.tools.genealogy.geo import registry
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace, ResolvedPlace


def _rp(score, ambiguous=False):
    return ResolvedPlace(name="X", place_type="Municipality", score=score,
                         ambiguous=ambiguous, source="s", query="q")


def test_route_france_uses_fr_resolver(monkeypatch):
    called = {}
    monkeypatch.setattr(registry, "resolve_fr", lambda p: called.setdefault("fr", _rp(1.0)))
    monkeypatch.setattr(registry, "resolve_world", lambda p: _rp(0.5))
    out = registry.resolve_place(ParsedPlace(raw="…", commune="Bourges",
                                             insee="18033", country="France"))
    assert out.score == 1.0 and "fr" in called          # FR autoritaire, pas de repli


def test_route_falls_back_to_world_when_country_resolver_returns_none(monkeypatch):
    monkeypatch.setattr(registry, "resolve_fr", lambda p: None)     # pas d'INSEE utilisable
    monkeypatch.setattr(registry, "resolve_world", lambda p: _rp(0.93))
    out = registry.resolve_place(ParsedPlace(raw="…", commune="X",
                                             insee=None, country="France", shifted=True))
    assert out.score == 0.93                             # repli mondial


def test_decide_action_thresholds():
    assert registry.decide_action(_rp(1.0), 0.90) == "ecrire"
    assert registry.decide_action(_rp(0.92), 0.90) == "ecrire"
    assert registry.decide_action(_rp(0.92, ambiguous=True), 0.90) == "proposition"
    assert registry.decide_action(_rp(0.80), 0.90) == "proposition"
    assert registry.decide_action(None, 0.90) == "indecidable"


def test_ambiguous_forces_proposition_even_at_score_1():
    rp = _rp(1.0, ambiguous=True)
    assert registry.decide_action(rp, 0.90) == "proposition"
    assert registry.confiance_of(rp) == "basse"
