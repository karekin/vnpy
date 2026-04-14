FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

COPY docker/tenx_hunter/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY config /workspace/config
COPY vnpy /workspace/vnpy
COPY examples/tenx_hunter_data_pipeline/sample_data /workspace/examples/tenx_hunter_data_pipeline/sample_data
COPY tests /workspace/tests
