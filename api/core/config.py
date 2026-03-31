import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://growtent:growtent@db:5432/growtent")
POLL_URL = os.getenv("POLL_URL", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
GO2RTC_BASE_URL = os.getenv("GO2RTC_BASE_URL", "http://go2rtc:1984")
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/project")
