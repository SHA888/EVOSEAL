# EVOSEAL File Reorganization Plan

## Current Issues

### Root Directory Problems
- **Too many markdown files** (16 .md files in root)
- **Mixed content types** - documentation, configuration, and project files mixed
- **Poor discoverability** - important docs buried among config files

### Docs Directory Problems
- **Flat structure** - 15+ files at root level of docs/
- **Inconsistent categorization** - related files not grouped
- **Redundant content** - some overlap with root-level docs

## Proposed Reorganization

### 1. Root Directory Cleanup
**Keep in Root:**
- `README.md` - Main project overview
- `LICENSE` - Legal requirement
- `CHANGELOG.md` - Version history
- `CONTRIBUTING.md` - Contribution guidelines
- `CODE_OF_CONDUCT.md` - Community standards

**Move to docs/:**
- `API_REFERENCE.md` → `docs/api/reference.md`
- `ARCHITECTURE.md` → `docs/architecture/overview.md` (merge with existing)
- `CONFIGURATION.md` → `docs/guides/configuration.md`
- `DEPLOYMENT.md` → `docs/guides/deployment.md`
- `DEVELOPMENT.md` → `docs/guides/development.md` (merge with existing)
- `MAINTAINERS.md` → `docs/project/maintainers.md`
- `ROADMAP.md` → `docs/project/roadmap.md`
- `SECURITY.md` → `docs/project/security.md`
- `SETUP.md` → `docs/guides/setup.md`
- `TESTING.md` → `docs/guides/testing.md`
- `TROUBLESHOOTING.md` → `docs/guides/troubleshooting.md`
- `CONTRIBUTORS.md` → `docs/project/contributors.md`

### 2. Docs Directory Restructuring

```
docs/
├── index.md                                    # Main documentation index
├── api/                                        # API Documentation
│   ├── index.md                               # API overview
│   └── reference.md                           # Full API reference (from root)
├── architecture/                               # Architecture Documentation
│   └── overview.md                            # Merged architecture docs
├── guides/                                     # User & Developer Guides
│   ├── quickstart.md                          # Quick start guide
│   ├── configuration.md                       # Configuration guide
│   ├── deployment.md                          # Deployment guide
│   ├── development.md                         # Development guide (merged)
│   ├── setup.md                               # Setup instructions
│   ├── testing.md                             # Testing guide
│   └── troubleshooting.md                     # Troubleshooting guide
├── safety/                                     # Safety & Security Documentation
│   ├── index.md                               # Safety overview
│   ├── rollback_safety.md                     # Rollback safety
│   ├── enhanced_rollback_logic.md             # Enhanced rollback
│   ├── rollback_manager_interface.md          # Rollback manager
│   ├── regression_detector_interface.md       # Regression detection
│   ├── statistical_regression_detection.md    # Statistical detection
│   ├── safety_validation.md                   # Safety validation
│   └── evolution_pipeline_safety_integration.md # Pipeline safety
├── core/                                       # Core System Documentation
│   ├── index.md                               # Core overview
│   ├── event_system.md                        # Event system
│   ├── error_handling.md                      # Error handling
│   ├── error_handling_resilience.md           # Resilience
│   ├── workflow_orchestration.md              # Workflow orchestration
│   ├── version_control_experiment_tracking.md # Version control
│   ├── agentic_system.md                      # Agentic system
│   ├── prompt_template_system.md              # Prompt templates
│   └── knowledge_base.md                      # Knowledge base
├── user/                                       # User Documentation
│   └── manual.md                              # User manual
├── examples/                                   # Example Documentation
│   └── quickstart.md                          # Example quickstart
└── project/                                    # Project Management
    ├── maintainers.md                         # Project maintainers
    ├── contributors.md                        # Contributors list
    ├── roadmap.md                             # Project roadmap
    └── security.md                            # Security policies
```

### 3. Benefits of Reorganization

#### Root Directory Benefits
- **Cleaner root** - Only essential project files
- **Better first impression** - Less overwhelming for new users
- **Standard compliance** - Follows open source conventions

#### Docs Directory Benefits
- **Logical grouping** - Related docs together
- **Better navigation** - Clear category structure
- **Scalable organization** - Easy to add new docs
- **Improved discoverability** - Users can find what they need

#### Maintenance Benefits
- **Easier updates** - Related docs in same location
- **Consistent structure** - Predictable organization
- **Better cross-references** - Related docs can link easily

## Implementation Steps

1. **Create new directory structure** in docs/
2. **Move and merge files** according to plan
3. **Update all internal links** in documentation
4. **Update README.md** with new doc structure
5. **Update mkdocs.yml** configuration
6. **Test all documentation links**
7. **Commit and push changes**

## Files to Review for Merging

### Potential Merges
- `ARCHITECTURE.md` + `docs/architecture/overview.md`
- `DEVELOPMENT.md` + `docs/guides/development.md`
- `API_REFERENCE.md` content review for `docs/api/reference.md`

### Content Deduplication
- Review for overlapping content between root and docs files
- Consolidate redundant information
- Ensure single source of truth for each topic
