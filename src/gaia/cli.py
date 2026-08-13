import json
from .runtime import GaiaRuntime, Hypothesis, MissionSpec


def main() -> None:
    spec = MissionSpec(mission_id="demo", budget=10, max_interventions=4, entropy_stop=0.05)
    hypotheses = [
        Hypothesis(name="voltage", probability=1/3, expected={"probe": 1.0}),
        Hypothesis(name="temperature", probability=1/3, expected={"probe": 0.5}),
        Hypothesis(name="load", probability=1/3, expected={"probe": 0.2}),
    ]
    runtime = GaiaRuntime(spec, hypotheses)
    runtime.choose_intervention([("probe", 0.8, 1.0), ("reset", 0.2, 2.0)])
    print(json.dumps({"mission": spec.mission_id, "entropy": runtime.entropy(), "trace_valid": runtime.verify_trace()}, indent=2))


if __name__ == "__main__":
    main()
