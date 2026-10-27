FROM ubuntu:24.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-yaml \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/dataset-platform/data-collection/data/7e2fa4b1 \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

WORKDIR /opt/dataset-platform/data-collection/data/7e2fa4b1
COPY data_collection.py gpu_backend.py gpu_run.py config.yaml ./
USER root
STOPSIGNAL SIGTERM
ENTRYPOINT ["python3", "-c", "import data_collection; data_collection.main()"]
