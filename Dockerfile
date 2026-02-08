FROM freqtradeorg/freqtrade:stable

# Install additional dependencies
USER root

RUN apt-get update && apt-get install -y \
    cron \
    nano \
    vim \
    curl \
    jq \
    wget \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    psycopg2-binary \
    schedule \
    python-telegram-bot \
    prometheus-client \
    redis

# Copy application files
COPY user_data /freqtrade/user_data
COPY scripts /freqtrade/scripts
COPY monitoring /freqtrade/monitoring

# Set permissions
RUN chmod +x /freqtrade/scripts/*.sh && \
    chmod +x /freqtrade/scripts/*.py

# Setup cron
COPY scripts/crontab /etc/cron.d/freqtrade-cron
RUN chmod 0644 /etc/cron.d/freqtrade-cron && \
    crontab /etc/cron.d/freqtrade-cron

# Create directories
RUN mkdir -p /freqtrade/logs \
    /freqtrade/hyperopt_results \
    /freqtrade/hyperopt_results/backups \
    /var/log \
    && touch /var/log/cron.log \
    && chown -R ftuser:ftuser /freqtrade/logs \
    /freqtrade/hyperopt_results \
    /freqtrade/scripts \
    /var/log/cron.log

USER ftuser

WORKDIR /freqtrade

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/ping || exit 1

# Expose ports
EXPOSE 8080 8081

# Default command
CMD ["bash", "-c", "cron && tail -f /var/log/cron.log & freqtrade trade --config user_data/config.json --strategy AdvancedFuturesSwingStrategy --logfile logs/freqtrade.log"]
