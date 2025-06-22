# EVOSEAL Examples

This directory contains examples and templates for using EVOSEAL.

## Basic Examples
- `quickstart.py`: Get started with EVOSEAL
- `logging_example.py`: Example of logging configuration
- `basic_usage.py`: Basic usage examples

## Workflows
- `basic_workflow.py`: Example workflow

## Project Templates
- `templates/basic/`: Basic project template with minimal configuration
  - `.evoseal/`: Configuration directory
  - `src/`: Source code directory
  - `tests/`: Test directory
  - `requirements.txt`: Project dependencies
  - `setup.py`: Project setup file

## Running Examples

To run an example:

```bash
# From the project root
python -m evoseal.examples.basic.quickstart
```

## Using Templates

To use a template as a starting point for your project:

```bash
# Copy the template to your new project directory
cp -r evoseal/examples/templates/basic my_new_project
cd my_new_project

# Install dependencies
pip install -r requirements.txt
```
