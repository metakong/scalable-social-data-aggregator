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
    dnsutils \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y openjdk-17-jdk unzip
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
RUN apt-get update && apt-get install -y --no-install-recommends unzip
# Install Android SDK and necessary build tools
RUN curl -o android-sdk.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
    && mkdir -p /opt/android-sdk \
    && unzip android-sdk.zip -d /opt/android-sdk \
    && mv /opt/android-sdk/cmdline-tools /opt/cmdline-tools \
    && rm android-sdk.zip \
    && export PATH="$PATH:/opt/cmdline-tools/bin" \
    && yes | /opt/cmdline-tools/bin/sdkmanager --licenses && /opt/cmdline-tools/bin/sdkmanager --install "build-tools;34.0.0" "platforms;android-34"
RUN echo "PATH: $PATH" && echo "ANDROID_HOME: $ANDROID_HOME"
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# This command will now correctly install browsers in a system-wide location.

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /home/app/web

COPY --chown=app:app backend/ .
COPY --chown=app:app entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app

EXPOSE 8000