# EVOSEAL Prompt Template System

## Overview

EVOSEAL uses a unified, file-based prompt template system to manage all agent, evaluation, and tool-related prompts. This system ensures modularity, flexibility, and versioning support for all prompt engineering workflows.

## Directory Structure

```
evoseal/prompt_templates/
  └── dgm/
      ├── diagnose_improvement_system_message.txt
      ├── diagnose_improvement_prompt.txt
      ├── tooluse_prompt.txt
      ├── self_improvement_instructions.txt
      ├── self_improvement_prompt_stochasticity.txt
      ├── self_improvement_prompt_emptypatches.txt
      ├── testrepo_test_command.txt
      └── testrepo_test_description.txt
  └── seal/   # (future)
  └── ...
```

Each `.txt` file contains a prompt template and a metadata header block with fields such as `category`, `version`, and `description`.

## Template Metadata Header

Each file should begin with a metadata header in YAML/JSON style:

```
# ---
# category: evaluation
# version: 1
# description: System message for diagnosing improvements in DGM agent
# ---
```

## TemplateManager API

The `TemplateManager` class (see `openevolve/openevolve/prompt/templates.py`) provides the following API:

- `get_template(key: str, version: Optional[int]=None) -> str`: Load a template by name (and optionally version).
- `get_metadata(key: str) -> dict`: Retrieve metadata for a template.
- `list_templates(category: Optional[str]=None) -> List[str]`: List all templates, optionally filtered by category.
- `get_by_category(category: str) -> List[str]`: List all templates in a category.
- `add_template(key: str, template: str, metadata: Optional[dict]=None)`: Add or update a template.

## Usage Example

```python
from openevolve.prompt.templates import TemplateManager
import os
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '../evoseal/prompt_templates/dgm')
template_manager = TemplateManager(TEMPLATE_DIR)

prompt = template_manager.get_template('diagnose_improvement_prompt')
meta = template_manager.get_metadata('diagnose_improvement_prompt')
print(meta['category'], meta['description'])
```

## Best Practices
- Always use file-based templates for all prompts.
- Use the metadata header for every template file.
- Use `TemplateManager` for all template loading and metadata access.
- Use categories and versions to organize and evolve prompt templates.

## Testing
- Unit tests for template loading, metadata parsing, and API are in `tests/unit/prompt_template/`.
