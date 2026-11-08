# Hugging Face Spaces (Docker SDK). Also runs anywhere Docker does:
#   docker build -t nyaya-saathi . && docker run -p 7860:7860 -e LLM_API_KEY=... nyaya-saathi
FROM python:3.12-slim

# Spaces run the container as user 1000; give it a home and a writable model cache.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1
WORKDIR /home/user/app

# CPU-only torch first (~200 MB instead of the ~2 GB CUDA build), then the rest.
RUN pip install --no-cache-dir torch==2.12.1 --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
USER user

# Build the search index inside the image (downloads the embedding model once, at build time),
# so the Space starts fast and no binary index files need to be uploaded.
RUN python scripts/build_index.py

EXPOSE 7860
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=7860", "--server.address=0.0.0.0", \
     "--server.headless=true", "--server.fileWatcherType=none"]
