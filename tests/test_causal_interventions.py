from gaia.causal_interventions import CausalEngine, CausalHypothesis, Intervention


def test_intervention_updates_causal_belief_from_observed_effect():
    engine = CausalEngine()
    engine.register(CausalHypothesis(
        name="heater-controls-temperature",
        predict=lambda state, intervention: {**state, "temperature": 30 if intervention.value else 20},
    ))

    result = engine.reconcile(
        "heater-controls-temperature",
        {"heater": False, "temperature": 20},
        Intervention("heater", True),
        {"heater": True, "temperature": 30},
        keys={"heater", "temperature"},
    )

    assert result["confirmed"] is True
    assert result["confidence"] == 1.0


def test_contradictory_observation_reduces_confidence():
    engine = CausalEngine()
    engine.register(CausalHypothesis(
        name="switch-controls-light",
        predict=lambda state, intervention: {**state, "light": "on" if intervention.value else "off"},
    ))
    engine.reconcile(
        "switch-controls-light",
        {"switch": False, "light": "off"},
        Intervention("switch", True),
        {"switch": True, "light": "on"},
    )
    result = engine.reconcile(
        "switch-controls-light",
        {"switch": False, "light": "off"},
        Intervention("switch", True),
        {"switch": True, "light": "off"},
    )
    assert result["confirmed"] is False
    assert result["confidence"] == 0.5
