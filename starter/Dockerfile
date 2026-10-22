# Lightweight image to run the Udatracker backend (and the frontend it
# serves) locally. Build and run from the starter/ directory:
#   docker build -t udatracker .
#   docker run --rm -p 5000:5000 udatracker
FROM python:3.12-slim

# No .pyc files in the image, unbuffered logs, and Flask debug mode off.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=0

WORKDIR /app

# Dependencies first, so this layer is cached while only the code changes.
# requirements.txt also pins pytest: the course ships one requirements file.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 5000

# app.run() binds 0.0.0.0, so the port is reachable from the host.
CMD ["python", "-m", "backend.app"]
