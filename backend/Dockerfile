FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VENV_PATH="/opt/venv"
ENV PATH="${VENV_PATH}/bin:${PATH}"

# This environment variable forces Playwright to install browsers system-wide,
# making them accessible to the non-root 'app' user. This permanently
# fixes the "Executable doesn't exist" error.
ENV PLAYWRIGHT_BROWSERS_PATH=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    build-essential \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv ${VENV_PATH}
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# This command will now correctly install browsers in a system-wide location.
RUN python -m playwright install --with-deps chromium

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /home/app/web

COPY --chown=app:app backend/ .
COPY --chown=app:app entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app

EXPOSE 8000