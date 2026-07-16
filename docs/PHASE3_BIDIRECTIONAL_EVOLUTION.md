# Phase 3: Bidirectional Continuous Evolution System

> **Two co-evolution paths.** This document describes the **weight-level** path
> (LoRA/QLoRA fine-tuning), which **requires a CUDA GPU** and historically targeted
> Mistral AI's Devstral — it is **not runnable on a CPU-only host**. For CPU hosts,
> EVOSEAL ships a **prompt-level** co-evolution loop (a coder model writes code, a
> reviewer model critiques it, and the critique evolves the coder's system prompt,
> regression-gated with rollback). See
> [`architecture/local_coevolution.md`](architecture/local_coevolution.md). Both
> paths share the same "improve → validate → roll back on regression" premise.

## Overview

EVOSEAL Phase 3 implements a bidirectional evolution system where EVOSEAL and its
coding model continuously improve each other through automated evolution cycles,
self-improvement (prompt-level on CPU, or weight-level fine-tuning on GPU), and
validation.

## Architecture

### Three-Phase System

#### Phase 1: Evolution Data Collection ✅
- **EvolutionDataCollector**: Async collection of evolution results from EVOSEAL's self-improvement cycles
- **PatternAnalyzer**: Extracts successful improvement strategies from evolution data
- **TrainingDataBuilder**: Generates training data in multiple formats (Alpaca, Chat, JSONL)
- **Data Models**: Comprehensive type-safe models for evolution tracking

#### Phase 2: Fine-tuning Infrastructure ✅
- **ModelFineTuner**: LoRA/QLoRA fine-tuning of the discovered coding model using evolution patterns (deprecated alias: `DevstralFineTuner`)
- **ModelValidator**: 5-category validation (functionality, quality, instruction following, safety, performance)
- **ModelVersionManager**: Version tracking, rollback, and comparison capabilities
- **TrainingManager**: Complete training pipeline coordination
- **BidirectionalEvolutionManager**: EVOSEAL ↔ local coding model orchestration

#### Phase 3: Continuous Improvement Loop ✅
- **ContinuousEvolutionService**: Main service orchestrating the complete evolution cycle
- **MonitoringDashboard**: Real-time web dashboard with WebSocket updates
- **systemd Integration**: Production-ready service management
- **Health Monitoring**: Continuous system health checks and error recovery

## System Components

### Continuous Evolution Service

The `ContinuousEvolutionService` is the heart of Phase 3, orchestrating:

- **Evolution Monitoring**: Checks for new evolution data every hour (configurable)
- **Training Orchestration**: Triggers fine-tuning when sufficient data is collected
- **Health Monitoring**: Continuous system health checks
- **Error Recovery**: Graceful error handling and recovery
- **Reporting**: Comprehensive evolution reports and statistics

### Real-time Monitoring Dashboard

Access at **http://localhost:9613** (when running via systemd):

#### Dashboard Features
- **Service Status**: Real-time system health, uptime, and operational state
- **Evolution Metrics**: Cycle counts, training progress, model improvements
- **Training Status**: Data readiness, sample counts, model versions
- **Performance Analytics**: Success rates, cycles per hour, efficiency metrics
- **Live Activity Log**: Real-time system events and notifications
- **WebSocket Updates**: Live data streaming without page refresh

#### Dashboard Sections
1. **Service Status Card**: Shows running state, uptime, last activity
2. **Evolution Metrics Card**: Displays evolution cycles, training cycles, improvements
3. **Training Status Card**: Shows training readiness, samples, model version
4. **Performance Card**: Cycles per hour, connected clients, data directory
5. **Activity Log**: Real-time scrolling log of system events

### systemd Integration

EVOSEAL Phase 3 runs as a production systemd user service:

#### Service Configuration
- **Service Name**: `evoseal.service`
- **Description**: "EVOSEAL Phase 3 Bidirectional Continuous Evolution Service"
- **Type**: Simple service with automatic restart
- **User Mode**: Runs as user service (no root required)
- **Auto-start**: Enabled with user linger for boot startup

#### Service Management Commands
```bash
# Check service status
systemctl --user status evoseal.service

# Start/stop/restart service
systemctl --user start evoseal.service
systemctl --user stop evoseal.service
systemctl --user restart evoseal.service

# View real-time logs
journalctl --user -fu evoseal.service

# Enable/disable auto-start
systemctl --user enable evoseal.service
systemctl --user disable evoseal.service
```

## Model Integration

### Ollama + local models (auto-discovered)

EVOSEAL Phase 3 integrates with Ollama and **discovers** its models by family
(see `evoseal/providers/local_models.py`), so it is not tied to any single tag.
Defaults on a CPU host:

- **Coder** (writes code): `deepseek-coder-v2:16b-lite-instruct-q8_0` (~16GB)
- **Reviewer** (critiques code): `qwen2.5-coder:7b-instruct-q6_K` (~6GB)
- **Override**: `EVOSEAL_CODER_MODEL` / `EVOSEAL_REVIEWER_MODEL`
- **Hardware**: prompt-level co-evolution runs CPU-only; the optional weight
  fine-tuning path needs a CUDA GPU (e.g. a single RTX 4090 or a 32GB Mac).

### Provider System

- **OllamaProvider**: Direct integration with local Ollama instance
- **local_models**: Per-role model discovery/resolution (matched by family)
- **Provider Manager**: Automatic provider selection and fallback
- **Health Checks**: Continuous monitoring of model availability
- **Configuration**: Configurable timeouts, temperature, and model parameters

## Deployment

### Quick Start

```bash
# Install Ollama and pull the coder + reviewer models (any coder/reviewer
# family works; EVOSEAL discovers them):
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull deepseek-coder-v2:16b-lite-instruct-q8_0
ollama pull qwen2.5-coder:7b-instruct-q6_K
ollama serve &

# Install Python dependencies
pip install aiohttp aiohttp-cors pydantic-settings

# Run health check
python3 scripts/run_phase3_continuous_evolution.py --health-check

# Start Phase 3 system
python3 scripts/run_phase3_continuous_evolution.py --verbose
```

### Production Deployment

The system is already configured for production deployment via systemd:

```bash
# Service is automatically configured and enabled
systemctl --user status evoseal.service

# Access monitoring dashboard
open http://localhost:9613
```

### Configuration Options

Phase 3 supports extensive configuration:

```bash
# Command line options
python3 scripts/run_phase3_continuous_evolution.py \
  --port=9613 \
  --evolution-interval=3600 \
  --training-interval=1800 \
  --min-samples=50 \
  --verbose
```

## Continuous Operation

### Evolution Cycles

- **Frequency**: Every 1 hour (configurable via `--evolution-interval`)
- **Process**:
  1. Check for new evolution data from EVOSEAL
  2. Analyze patterns and improvement strategies
  3. Update evolution statistics
  4. Log activity and update dashboard

### Training Cycles

- **Frequency**: Every 30 minutes (configurable via `--training-interval`)
- **Trigger**: When sufficient evolution samples collected (default: 50)
- **Process**:
  1. Check training readiness
  2. Prepare training data from evolution patterns
  3. Execute LoRA/QLoRA fine-tuning
  4. Validate fine-tuned model
  5. Update model version and deploy if validation passes
  6. Rollback if validation fails

### Health Monitoring

- **Service Health**: Continuous monitoring of service components
- **Model Health**: Regular checks of Ollama/coding-model availability
- **Error Recovery**: Automatic restart and error handling
- **Logging**: Comprehensive logging to files and systemd journal

## Data Flow

### Bidirectional Evolution Loop

```
EVOSEAL Evolution → Data Collection → Pattern Analysis → Training Data
                                                              ↓
Model Deployment ← Validation ← Fine-tuning ← Training Manager
        ↓
Improved coding model → Better EVOSEAL Performance → More Evolution Data
```

### Data Storage

- **Evolution Data**: `data/continuous_evolution/evolution_data/`
- **Training Data**: `data/continuous_evolution/bidirectional/training/`
- **Model Versions**: `data/continuous_evolution/bidirectional/training/versions/`
- **Reports**: `data/continuous_evolution/bidirectional/evolution_report_*.json`
- **Logs**: `/home/kade/EVOSEAL/logs/`

## Monitoring and Metrics

### Key Metrics

- **Evolution Cycles Completed**: Total number of evolution monitoring cycles
- **Training Cycles Triggered**: Number of fine-tuning cycles initiated
- **Successful Improvements**: Models that passed validation and were deployed
- **Success Rate**: Percentage of training cycles resulting in improvements
- **Cycles per Hour**: Evolution monitoring frequency
- **Uptime**: Total service operational time

### Performance Analytics

- **Improvement Rate**: Successful improvements per training cycle
- **Evolution Efficiency**: Evolution cycles per successful improvement
- **Model Quality Trends**: Validation scores over time
- **System Utilization**: Resource usage and performance metrics

## Troubleshooting

### Common Issues

1. **Port 9613 in use**
   - Solution: Use `--port` flag to specify different port
   - Check: `netstat -tlnp | grep :9613`

2. **Ollama not running**
   - Solution: Start Ollama with `ollama serve &`
   - Check: `curl http://localhost:11434/api/tags`

3. **Coder/reviewer model not found**
   - Solution: pull a coder + reviewer model, e.g.
     `ollama pull deepseek-coder-v2:16b-lite-instruct-q8_0` and
     `ollama pull qwen2.5-coder:7b-instruct-q6_K`
   - Check: `ollama list`

4. **systemd service failing**
   - Check logs: `journalctl --user -xeu evoseal.service`
   - Check status: `systemctl --user status evoseal.service`

### Health Check

Run comprehensive health check:

```bash
python3 scripts/run_phase3_continuous_evolution.py --health-check
```

### Log Analysis

```bash
# Service logs
journalctl --user -fu evoseal.service

# Application logs
tail -f /home/kade/EVOSEAL/logs/phase3_continuous_evolution.log

# Error logs
tail -f /home/kade/EVOSEAL/logs/evoseal-error.log
```

## API Reference

### Dashboard API Endpoints

- `GET /`: Main dashboard page
- `GET /api/status`: Service status JSON
- `GET /api/metrics`: Current metrics JSON
- `GET /api/report`: Comprehensive report JSON
- `GET /ws`: WebSocket connection for real-time updates

### WebSocket Messages

```json
{
  "type": "metrics_update",
  "data": {
    "service_status": {...},
    "evolution_status": {...},
    "training_status": {...}
  },
  "timestamp": "2025-01-27T00:53:00Z"
}
```

## Security

### Safety Controls

- **Model Validation**: 5-category testing including safety and alignment
- **Rollback Protection**: Automatic rollback on validation failure
- **User Service**: Runs as user service, no root privileges required
- **Local Operation**: All processing local, no external API calls required
- **Input Validation**: Comprehensive input validation and sanitization

### Network Security

- **Local Dashboard**: Dashboard only accessible on localhost
- **No External Access**: No external network access required for operation
- **Ollama Local**: Model inference entirely local via Ollama

## Future Enhancements

### Planned Features

- **Multi-model Support**: Support for additional coding models
- **Advanced Analytics**: More sophisticated performance analytics
- **Human-in-the-loop**: Interactive approval for model deployments
- **Distributed Operation**: Support for distributed fine-tuning
- **Model Comparison**: Side-by-side model performance comparison

### Extensibility

The Phase 3 system is designed for extensibility:

- **Plugin Architecture**: Easy addition of new validation tests
- **Provider System**: Support for additional model providers
- **Dashboard Extensions**: Customizable dashboard components
- **Metric Collection**: Extensible metrics and reporting system

## Conclusion

EVOSEAL Phase 3 represents a complete bidirectional continuous evolution system that enables EVOSEAL and its local coding model to continuously improve each other through automated evolution cycles, self-improvement, and validation. The system is production-ready with comprehensive monitoring, error handling, and systemd integration.

The real-time monitoring dashboard provides full visibility into the evolution process, while the systemd integration ensures reliable operation in production environments. The bidirectional nature of the system creates a positive feedback loop where improvements in one system benefit the other, leading to continuous advancement in both EVOSEAL's capabilities and the coding model's performance on coding tasks.
