#\!/bin/bash
# Force trading to be disabled at startup
redis-cli set trading_enabled false
echo "Forced trading to DISABLED state for safety"
