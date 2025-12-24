"""
Friday 3.0 Constants

Shared constants used across the codebase.
"""

from datetime import timezone, timedelta

# Brazil timezone (UTC-3) - Sao Paulo
BRT = timezone(timedelta(hours=-3))

# Default timeout for HTTP requests (seconds)
DEFAULT_HTTP_TIMEOUT = 10.0

# Default timeout for long-running operations (seconds)
LONG_OPERATION_TIMEOUT = 30.0
