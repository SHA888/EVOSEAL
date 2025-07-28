# EVOSEAL v0.3.2 - Port Consistency and Configuration Standardization

*Released on: 2025-07-27*

## 🔧 Fixes

### Port Standardization
- **Consistent Default Port**: Standardized all components to use port **8081** by default
- **Eliminated Confusion**: Removed mixed references between ports 8080 and 8081
- **Universal Configuration**: All code, documentation, and deployment scenarios now use 8081

### Code Updates
- **MonitoringDashboard**: Updated default port from 8080 to 8081
- **Phase3Orchestrator**: Updated default port from 8080 to 8081
- **Argument Parser**: Updated default port help text and value to 8081
- **SEALConfig**: Updated dashboard_port default from 8080 to 8081

### Documentation Updates
- **Deployment Guide**: Updated development URLs from 8080 to 8081
- **API Reference**: Updated base URLs for consistency
- **systemd Template**: Already using 8081 (no change needed)
- **README**: Already consistent (no change needed)

### WebSocket Stability Improvements
- **JSON Serialization Fix**: Added custom datetime serializer for WebSocket messages
- **Connection Stability**: Resolved WebSocket disconnection issues caused by serialization errors
- **Real-time Updates**: Improved reliability of live dashboard updates

## 🎯 Benefits

- ✅ **Consistent Experience**: Same port across all deployment scenarios
- ✅ **Reduced Conflicts**: Port 8081 has fewer conflicts than 8080
- ✅ **Clear Documentation**: No more confusion about which port to use
- ✅ **Simplified Deployment**: Single port configuration for all environments
- ✅ **Stable WebSocket**: Reliable real-time dashboard updates

## 🔄 Migration Notes

### For Existing Users
- Dashboard remains accessible at current Tailscale IP on port 8081
- All existing functionality preserved
- No action required for most users

### For New Deployments
- All components now default to port 8081
- Documentation consistently references port 8081
- Simplified configuration with single standard port

## 📊 Port Configuration

- **Development**: `http://localhost:8081`
- **Production**: `http://<tailscale-ip>:8081`
- **systemd Service**: Configured for port 8081
- **Default Settings**: All defaults set to 8081

## 🛠️ Technical Details

### Files Updated
- `evoseal/services/monitoring_dashboard.py` - Default port and JSON serialization
- `scripts/run_phase3_continuous_evolution.py` - Default port and help text
- `evoseal/config/settings.py` - SEALConfig default port
- `docs/DEPLOYMENT_GUIDE.md` - Development URLs
- `docs/API_REFERENCE.md` - Base URLs

### Backward Compatibility
- Existing command-line usage with explicit `--port` arguments remains unchanged
- Configuration files with explicit port settings are respected
- Only default values have been updated

---

**This release ensures consistent port configuration across all EVOSEAL components and improves WebSocket reliability.**
