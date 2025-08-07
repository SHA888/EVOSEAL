#!/bin/bash

# Update all references from 'venv' to '.venv' in markdown and shell script files
find /home/kd/EVOSEAL -type f \( -name "*.md" -o -name "*.sh" \) \
  -exec sed -i 's/venv\/bin\/activate/.venv\/bin\/activate/g' {} \;

# Update the setup script specifically for the activation command
sed -i 's/source venv\/bin\/activate/source .venv\/bin\/activate/g' /home/kd/EVOSEAL/scripts/setup.sh

# Update the setup script completion message
sed -i 's/venv\/bin\/activate/.venv\/bin\/activate/g' /home/kd/EVOSEAL/scripts/setup.sh

echo "✅ Updated all virtual environment references to use .venv"
