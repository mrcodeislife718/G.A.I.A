from gaia import Evidence, GaiaRuntime, Hypothesis, MissionSpec


def test_belief_revision_and_trace_integrity():
    runtime = GaiaRuntime(
        MissionSpec(mission_id="m1", budget=5, max_interventions=2, entropy_stop=0.1),
        [
            Hypothesis(name="a", probability=0.5, expected={"sensor": 1.0}),
            Hypothesis(name="b", probability=0.5, expected={"sensor": 0.0}),
        ],
    )
    evidence = Evidence(evidence_id="e1", kind="sensor", value=1.0, provenance="test")
    runtime.admit(evidence, lambda h, e: 0.95 if h.name == "a" else 0.05)
    assert runtime.hypotheses[0].probability > 0.9
    assert runtime.verify_trace()


def test_budget_binds_interventions():
    runtime = GaiaRuntime(MissionSpec(mission_id="m2", budget=1, max_interventions=5, entropy_stop=0), [Hypothesis(name="a", probability=1, expected={})])
    assert runtime.choose_intervention([("cheap", 1.0, 1.0)]) == "cheap"
    assert runtime.choose_intervention([("more", 1.0, 1.0)]) is None
