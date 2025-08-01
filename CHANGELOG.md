# Changelog

All notable changes to the EVOSEAL project are documented here.

## [0.3.6] - 2025-08-01 - Port Conflict Resolution and Documentation Updates

### 🔧 Fixes

#### Port Configuration
- **Port Conflict Resolution**: Changed default port from 8081 to 9613 to resolve conflicts
- **Documentation Updates**: Ensured all documentation reflects the new port number
- **Systemd Service**: Updated service template to use the new port

### 📚 Documentation
- **API Reference**: Updated all API endpoint URLs to use port 9613
- **Deployment Guide**: Updated port references in deployment instructions
- **README**: Updated quick start and monitoring sections with new port

### 🚀 Deployment
- **Systemd Service**: Updated template with new port configuration
- **Configuration**: Ensured backward compatibility with existing deployments


## [0.3.2] - 2025-07-27 - Port Consistency and Configuration Standardization

### 🔧 Fixes

#### Port Standardization
- **Consistent Default Port**: Standardized all components to use port **9613** by default
- **Eliminated Confusion**: Removed mixed references between ports 8080 and 8081
- **Universal Configuration**: All code, documentation, and deployment scenarios now use 9613

#### Code Updates
- **MonitoringDashboard**: Updated default port from 8080 to 9613
- **Phase3Orchestrator**: Updated default port from 8080 to 9613
- **Argument Parser**: Updated default port help text and value to 9613
- **SEALConfig**: Updated dashboard_port default from 8080 to 9613

#### Documentation Updates
- **Deployment Guide**: Updated development URLs from 8080 to 9613
- **API Reference**: Updated base URLs for consistency
- **systemd Template**: Updated to use port 9613
- **README**: Already consistent (no change needed)

### 🎯 Benefits

- ✅ **Consistent Experience**: Same port across all deployment scenarios
- ✅ **Reduced Conflicts**: Port 9613 has fewer conflicts than 8081
- ✅ **Clear Documentation**: No more confusion about which port to use
- ✅ **Simplified Deployment**: Single port configuration for all environments

### 🔄 Migration Notes

#### For Existing Users
- Systemd service now uses port 9613
- Dashboard remains accessible at current Tailscale IP on port 9613
- All existing functionality preserved

#### For New Deployments
- All components now default to port 9613
- Documentation consistently references port 9613
- Simplified configuration with single standard port

### 📊 Port Configuration

- **Development**: `http://localhost:9613`
- **Production**: `http://<tailscale-ip>:9613`
- **systemd Service**: Configured for port 9613
- **Default Settings**: All defaults set to 9613

## [0.3.1] - 2025-07-27 - Portable systemd Service Configuration

### 🔧 Improvements

#### Portable systemd Service
- **Removed Hardcoded Paths**: Replaced `/home/kade` with systemd specifier `%h` for universal compatibility
- **Dynamic Tailscale IP Detection**: Auto-detects Tailscale IP with graceful fallback to localhost
- **Universal Deployment**: Service now works for any user on any machine without modification
- **Template Creation**: Added `systemd/evoseal.service.template` for easy deployment

#### Enhanced Script Support
- **Host Parameter**: Added `--host` argument to Phase 3 script for flexible binding
- **Orchestrator Updates**: Enhanced Phase3Orchestrator to support configurable dashboard host
- **Auto-Detection Logic**: Intelligent network interface detection with fallback mechanisms

### 🛠️ Technical Changes

#### systemd Configuration
- **Portable Paths**: All paths now use `%h` systemd specifier
- **Environment Variables**: Updated to use portable path references
- **Service Target**: Fixed `WantedBy=default.target` for proper user service enablement
- **Dynamic IP**: `$(tailscale ip -4 2>/dev/null || echo "localhost")` for automatic network detection

#### Documentation Updates
- **systemd Integration Guide**: Updated with portable configuration examples
- **Deployment Instructions**: Enhanced with universal deployment steps
- **Template Documentation**: Added guidance for cross-platform deployment

### 🎯 Benefits

- ✅ **Zero Configuration**: Works out-of-the-box for any user
- ✅ **Cross-Platform**: Compatible with any Linux distribution and user setup
- ✅ **Network Agnostic**: Automatically adapts to Tailscale or localhost
- ✅ **Community Ready**: Easy deployment for open-source distribution

### 🔄 Migration Notes

#### For Existing Users
- Service automatically uses new portable configuration
- No manual intervention required for existing installations
- Dashboard remains accessible at detected network interface

#### For New Deployments
- Copy `systemd/evoseal.service.template` to `~/.config/systemd/user/evoseal.service`
- Run standard systemd enable/start commands
- Service automatically detects user environment and network configuration

## [0.3.0] - 2025-07-27 - Phase 3: Bidirectional Continuous Evolution

### 🚀 Major Features Added

#### Phase 3 Continuous Improvement Loop
- **ContinuousEvolutionService**: Automated bidirectional evolution system
  - Continuous monitoring of EVOSEAL ↔ Devstral evolution cycles
  - Automated training orchestration with configurable intervals
  - Health monitoring and graceful error handling
  - Comprehensive statistics and reporting

#### Real-time Monitoring Dashboard
- **MonitoringDashboard**: Web-based real-time monitoring interface
  - Live WebSocket updates every 30 seconds
  - Comprehensive metrics visualization
  - Service status, evolution progress, and training status
  - Modern responsive UI with dark theme
  - REST API endpoints for programmatic access

#### systemd Integration
- **Production Deployment**: Full systemd user service integration
  - Automatic startup on boot with user linger
  - Robust restart policies and error recovery
  - Comprehensive logging to files and systemd journal
  - Environment variable configuration
  - Service management commands

#### Phase 2 Fine-tuning Infrastructure (Completed)
- **DevstralFineTuner**: LoRA/QLoRA fine-tuning with GPU/CPU fallback
- **TrainingManager**: Complete training pipeline coordination
- **ModelValidator**: 5-category comprehensive validation suite
- **ModelVersionManager**: Version tracking, rollback, and comparison
- **BidirectionalEvolutionManager**: EVOSEAL ↔ Devstral orchestration

### 🔧 Technical Improvements

#### Architecture
- Modular Phase 3 service architecture with clear separation of concerns
- Async/await throughout for scalable continuous operation
- Comprehensive error handling and graceful degradation
- Fallback mechanisms for limited hardware environments
- Integration with existing EVOSEAL provider system

#### Configuration Management
- **SEALConfig**: Centralized configuration with pydantic v2
- Environment variable support with defaults
- Configurable evolution and training intervals
- Port configuration for dashboard deployment
- Ollama provider integration settings

#### Data Management
- Structured data directories for evolution and training data
- Model version management with automatic cleanup
- Evolution report generation with trends and recommendations
- Comprehensive logging with rotation support

### 📚 Documentation

#### New Documentation
- **PHASE3_BIDIRECTIONAL_EVOLUTION.md**: Complete Phase 3 architecture guide
- **SYSTEMD_INTEGRATION.md**: systemd service setup and management
- **DEPLOYMENT_GUIDE.md**: Comprehensive deployment instructions
- **API_REFERENCE.md**: REST API and WebSocket documentation

#### Updated Documentation
- **README.md**: Updated with Phase 3 features and quick start
- Enhanced project structure documentation
- Added troubleshooting and maintenance guides

### 🛠️ Dependencies

#### Added
- `aiohttp>=3.8.0`: Async HTTP server for dashboard
- `aiohttp-cors`: CORS support for web interface
- `pydantic-settings>=2.0.0`: Enhanced configuration management

#### Updated
- Enhanced Ollama integration with Devstral model
- Improved provider management system
- Better error handling for optional dependencies

### 🔒 Security & Reliability

#### Security
- systemd user service (no root privileges required)
- localhost-only dashboard binding
- NoNewPrivileges systemd directive
- Local-only operation (no external API calls)

#### Reliability
- Automatic service restart on failure
- Comprehensive health checks
- Graceful shutdown handling
- Rollback support for model versions
- Extensive logging and monitoring

### 🐛 Bug Fixes
- Fixed port conflicts by changing default dashboard port to 9613
- Resolved transformers dependency issues with fallback modes
- Fixed test failures in Phase 2 components
- Corrected data model integration issues
- Enhanced error handling for missing GPU/transformers

### 🔄 Migration Notes

#### From Previous Versions
- Legacy `evoseal.service` replaced with Phase 3 system
- New dashboard accessible on port 9613 (configurable)
- Updated service management commands
- New data directory structure

#### Breaking Changes
- systemd service now runs Phase 3 system instead of legacy runner
- Dashboard port changed from 8081 to 9613 by default
- New configuration structure with pydantic v2

### 📊 Performance
- Optimized continuous evolution loop with configurable intervals
- Efficient WebSocket updates for real-time monitoring
- Reduced resource usage with smart scheduling
- Improved memory management for long-running operations

### 🎯 Next Steps
- Monitor Phase 3 operation in production
- Optimize fine-tuning parameters based on real data
- Extend monitoring with advanced analytics
- Implement automated backup and recovery

## [0.2.8] - 2025-07-23

### Added
- Automated release workflow with GitHub Actions
- Comprehensive release checklist
- Pre-release and release workflow integration
- Version management system
- Automated release notes generation

### Changed
- Updated version to 0.2.8
- Enhanced release process documentation
- Improved error handling in release scripts

### Fixed
- Version bumping logic in auto_evolve_and_push.sh
- Duplicate function definitions in release scripts

## [Older Versions]

All notable changes to the EVOSEAL project are documented in the [releases](./releases) folder.
