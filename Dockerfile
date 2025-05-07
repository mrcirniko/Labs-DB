FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    make \
    git \
    libpq-dev \
    postgresql-server-dev-15 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/pgbigm/pg_bigm.git /tmp/pg_bigm && \
    cd /tmp/pg_bigm && \
    make USE_PGXS=1 && \
    make USE_PGXS=1 install && \
    rm -rf /tmp/pg_bigm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY load_data.py .

CMD ["python", "load_data.py"]
