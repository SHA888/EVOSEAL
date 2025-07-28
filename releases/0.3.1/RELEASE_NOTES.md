# EVOSEAL v0.3.1 - Portable systemd Service Configuration

*Released on: 2025-07-27*

## 🔧 Improvements

### Portable systemd Service
- **Removed Hardcoded Paths**: Replaced `/home/kade` with systemd specifier `%h` for universal compatibility
- **Dynamic Tailscale IP Detection**: Auto-detects Tailscale IP with graceful fallback to localhost
- **Universal Deployment**: Service now works for any user on any machine without modification
- **Template Creation**: Added `systemd/evoseal.service.template` for easy deployment

### Enhanced Script Support
- **Host Parameter**: Added `--host` argument to Phase 3 script for flexible binding
- **Orchestrator Updates**: Enhanced Phase3Orchestrator to support configurable dashboard host
- **Auto-Detection Logic**: Intelligent network interface detection with fallback mechanisms

## 🛠️ Technical Changes

### systemd Configuration
- **Portable Paths**: All paths now use `%h` systemd specifier
- **Environment Variables**: Updated to use portable path references
- **Service Target**: Fixed `WantedBy=default.target` for proper user service enablement
- **Dynamic IP**: `$(tailscale ip -4 2>/dev/null || echo "localhost")` for automatic network detection

### Documentation Updates
- **systemd Integration Guide**: Updated with portable configuration examples
- **Deployment Instructions**: Enhanced with universal deployment steps
- **Template Documentation**: Added guidance for cross-platform deployment

## 🎯 Benefits

### For Existing Deployments
- Automatic migration to portable configuration
- No manual intervention required for existing installations
- Dashboard remains accessible at detected network interface

### For New Deployments
- Copy `systemd/evoseal.service.template` to `~/.config/systemd/user/evoseal.service`
- Run standard systemd enable/start commands
- Service automatically detects user environment and network configuration

## 🔧 Migration Guide

### Automatic Migration
Existing services will automatically use the new portable configuration on next restart:

```bash
systemctl --user restart evoseal
```

### Manual Setup for New Users
```bash
# Copy template to user systemd directory
cp systemd/evoseal.service.template ~/.config/systemd/user/evoseal.service

# Enable and start service
systemctl --user enable evoseal
systemctl --user start evoseal
```

## 📊 Compatibility

- **Works on any Linux distribution** with systemd
- **Any user account** - no hardcoded paths
- **Tailscale or localhost** - automatic network detection
- **Preserves all functionality** from v0.3.0

---

**This release makes EVOSEAL deployment truly portable and user-agnostic.**
