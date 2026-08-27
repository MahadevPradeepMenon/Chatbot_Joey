# syntax=docker/dockerfile:1

FROM python:3.12-slim

ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG TORCH_VERSION=2.12.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

RUN groupadd --system joey \
    && useradd \
        --system \
        --gid joey \
        --create-home \
        --home-dir /home/joey \
        joey

COPY requirements.txt /app/requirements.txt

# Joey uses CPU inference. Installing the CPU wheel first prevents pip from
# pulling the much larger CUDA-enabled PyTorch dependency stack.
RUN python -m pip install --upgrade pip \
    && python -m pip install \
        "torch==${TORCH_VERSION}" \
        --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install \
        --requirement /app/requirements.txt

COPY --chown=joey:joey . /app

RUN mkdir -p \
        /app/data/indexes \
        /app/data/local \
        /app/data/synthetic \
        /opt/huggingface \
    && chown -R joey:joey \
        /app \
        /opt/huggingface

USER joey

# Preload the local embedding model during image build so the first strategy
# request does not need to download the model.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}', device='cpu')"
# The same image is used for the API and Streamlit services; Compose
# overrides the command for the frontend service.
EXPOSE 8000 8501

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
