# This script will update the MockEvaluator in test_controller_full_run to include 'fitness' in the metrics dictionary

# Read the test file
with open("/home/kd/EVOSEAL/tests/integration/test_openevolve_controller.py") as f:
    content = f.read()

# Update the MockEvaluator in test_controller_full_run
updated_content = content.replace(
    '    class MockEvaluator(Evaluator):\n        def evaluate(self, program):\n            return {\n                "fitness": 0.9,  # Fixed fitness for testing\n                "metrics": {"accuracy": 0.9, "latency": 0.1},\n                "passed": True\n            }',
    '    class MockEvaluator(Evaluator):\n        def evaluate(self, program):\n            return {\n                "fitness": 0.9,  # Fixed fitness for testing\n                "metrics": {"fitness": 0.9, "accuracy": 0.9, "latency": 0.1},\n                "passed": True\n            }',
    1,  # Only replace the first occurrence (in test_controller_full_run)
)

# Write the updated content back to the file
with open("/home/kd/EVOSEAL/tests/integration/test_openevolve_controller.py", "w") as f:
    f.write(updated_content)
