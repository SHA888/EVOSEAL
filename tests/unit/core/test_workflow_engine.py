import json

import pytest

from evoseal.core.errors import ValidationError
from evoseal.core.workflow import StepConfig, WorkflowConfig, WorkflowEngine, WorkflowStatus


class DummyComponent:
    def __init__(self):
        self.calls = []

    def process(self, x):
        self.calls.append(x)
        return x * 2

    def fail(self, x):
        raise ValueError("fail")


def test_register_and_execute_workflow():
    engine = WorkflowEngine()
    engine.register_component("dummy", DummyComponent())
    steps = [
        StepConfig(name="step1", component="dummy", method="process", params={"x": 3}),
        StepConfig(name="step2", component="dummy", method="process", params={"x": 5}),
    ]
    engine.define_workflow("simple", steps)
    engine.execute_workflow("simple")
    assert engine.status.name in ("COMPLETED", "RUNNING")


def test_workflow_step_failure_and_error_handling():
    engine = WorkflowEngine()
    engine.register_component("dummy", DummyComponent())
    steps = [
        StepConfig(name="fail", component="dummy", method="fail", params={"x": 1}),
    ]
    engine.define_workflow("failflow", steps)
    engine.execute_workflow("failflow")
    assert engine.status == WorkflowStatus.FAILED


def test_schema_validation(tmp_path):
    from pathlib import Path

    from jsonschema import ValidationError as JsonValidationError
    from jsonschema import validate

    # Load schemas
    schema_dir = Path(__file__).parents[3] / "evoseal" / "schemas"
    with open(schema_dir / "code_change_schema.json") as f:
        code_change_schema = json.load(f)
    with open(schema_dir / "evaluation_result_schema.json") as f:
        eval_schema = json.load(f)
    with open(schema_dir / "config_schema.json") as f:
        config_schema = json.load(f)
    # Valid code change
    code_change = {
        "file_path": "foo.py",
        "change_type": "modify",
        "content": "print('hi')",
    }
    validate(instance=code_change, schema=code_change_schema)
    # Invalid code change (missing file_path)
    with pytest.raises(JsonValidationError):
        validate(
            instance={"change_type": "modify", "content": "x"},
            schema=code_change_schema,
        )
    # Valid evaluation result
    eval_result = {"test_id": "t1", "status": "pass", "metrics": {"accuracy": 0.9}}
    validate(instance=eval_result, schema=eval_schema)
    # Invalid evaluation result (missing metrics)
    with pytest.raises(JsonValidationError):
        validate(instance={"test_id": "t2", "status": "pass"}, schema=eval_schema)
    # Valid config
    config = {"dgm": {}, "openevolve": {}, "seal": {}, "integration": {}}
    validate(instance=config, schema=config_schema)
    # Invalid config (missing dgm)
    with pytest.raises(JsonValidationError):
        validate(
            instance={"seal": {}, "integration": {}, "openevolve": {}},
            schema=config_schema,
        )
