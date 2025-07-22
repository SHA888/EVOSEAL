# Extended EVOSEAL Capabilities Guide

This document outlines the enhanced capabilities added to the EVOSEAL system, focusing on two key areas:
1. Additional data sources for self-evolution
2. External project evolution capabilities

## 1. Adding Data Sources for EVOSEAL Learning

EVOSEAL can now learn from multiple data sources beyond its own codebase. These additional sources enhance its ability to generate high-quality improvements.

### Available Data Source Integration Methods

#### External Code Repositories

The `integrate_external_sources.sh` script allows EVOSEAL to learn from external code repositories:

```bash
# Run with default settings
./scripts/integrate_external_sources.sh

# Specify a custom target directory
./scripts/integrate_external_sources.sh /path/to/custom/dir
```

**Configuration**: External repositories are defined in `config/external_repositories.txt` with the format:
```
repository_url,branch,subdirectory,description
```

The script will automatically:
1. Clone or update the specified repositories
2. Extract relevant knowledge from specified subdirectories
3. Generate metadata and structural information
4. Update the EVOSEAL configuration to include these sources

#### Learning Datasets

The `sync_learning_datasets.sh` script integrates curated learning datasets:

```bash
# Run with default configuration
./scripts/sync_learning_datasets.sh

# Use custom configuration file
./scripts/sync_learning_datasets.sh path/to/custom_config.json
```

**Configuration**: Learning datasets are defined in `config/learning_datasets.json` and include:
- Algorithm implementations
- Design patterns
- Machine learning best practices
- Custom company code standards

### Adding Your Own Knowledge Sources

1. **Custom Knowledge Directory**:
   ```bash
   mkdir -p data/knowledge/my_custom_knowledge
   # Add relevant files and code samples
   ```

2. **Environment Configuration**:
   Add the path to your `.env` file:
   ```
   SEAL_KNOWLEDGE_BASE=data/knowledge:data/knowledge/my_custom_knowledge
   ```

3. **Direct Configuration Update**:
   Edit `.evoseal/config.yaml` to include additional knowledge paths:
   ```yaml
   knowledge_paths:
     - data/knowledge
     - path/to/your/knowledge
   ```

## 2. Using EVOSEAL to Evolve External Projects

EVOSEAL can now be applied to evolve external projects rather than focusing on its own codebase.

### Setup Process

1. **Create Project Configuration**:
   ```bash
   cp templates/project_evolution.json my_project_config.json
   # Edit my_project_config.json with your project details
   ```

2. **Run Project Evolution**:
   ```bash
   ./scripts/evolve_project.sh my_project_config.json 10
   ```
   The second parameter (10) specifies the number of iterations.

### Configuration Options

The project evolution configuration includes:

#### Project Details
```json
"project": {
  "repository": "https://github.com/username/project.git",
  "local_path": "/path/to/local/clone",
  "branch": "evoseal-evolution",
  "base_branch": "main"
}
```

#### Evolution Focus
```json
"evolution": {
  "focus_areas": [
    "performance_optimization",
    "code_quality",
    "test_coverage",
    "documentation"
  ],
  "target_files": [
    "src/**/*.py",
    "lib/**/*.js",
    "!**/test_*.py"
  ]
}
```

#### Evaluation Metrics
```json
"evaluation": {
  "metrics": [
    {
      "name": "code_quality",
      "tool": "pylint",
      "command": "pylint {target_dir} --output-format=json",
      "threshold": 8.0,
      "higher_is_better": true
    }
  ]
}
```

#### Version Control Integration
```json
"version_control": {
  "auto_commit": true,
  "commit_message_template": "EVOSEAL: {improvement_type} improvement in {component}"
}
```

#### Safety Boundaries
```json
"safety": {
  "max_file_changes_per_iteration": 5,
  "max_line_changes_per_file": 50,
  "restricted_files": [
    "config/security.json",
    "**/*password*",
    "**/*.key"
  ]
}
```

### Results and Monitoring

EVOSEAL produces detailed logs and results for external project evolution:

- **Logs**: Available in `logs/projects/evolution_*.log`
- **Metrics**: Stored in `results/projects/metrics_*.json`
- **Results**: Complete evolution results in `results/projects/result_*.json`

### Example Workflow

1. Clone a repository you want to improve
2. Create a project configuration file
3. Run the evolution script
4. Review the proposed changes
5. Optionally commit and create a PR
6. Merge improvements back to the main branch

## Integration with Continuous Operation

Both capabilities are designed to work with the continuous operation setup:

1. **Add Scheduled Data Source Updates**:
   Add to `scripts/auto_evolve_and_push.sh` to periodically refresh data sources.

2. **Project Queue Processing**:
   Set up a queue of projects to be evolved in sequence.

## Troubleshooting

If you encounter issues:

1. Check log files in `logs/` directory
2. Verify proper repository access and permissions
3. Ensure metrics tools are installed
4. Check that target files exist and match patterns
5. Verify EVOSEAL is correctly activated in the virtual environment

---

For additional support, refer to the main EVOSEAL documentation.
