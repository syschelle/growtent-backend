FROM python:3.12-slim

# Avoid Python bytecode writes on the read-only runtime root filesystem.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Project ZIPs may contain mode-0600 files; make non-secret application code
# readable for the optional numeric non-root runtime user.
RUN chmod -R a+rX /app

# Keep existing root-owned ./data mounts compatible on automatic upgrades.
# Deployments with suitable /data ownership can set user: "10001:10001" in
# an API Compose override after verifying all write paths.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers"]
