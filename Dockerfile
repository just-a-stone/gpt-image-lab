FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements-webui.txt ./
RUN pip install --no-cache-dir -r requirements-webui.txt

COPY . .

RUN mkdir -p output

EXPOSE 8787

CMD ["python", "-m", "uvicorn", "codex_image.webui.app:app", \
     "--host", "0.0.0.0", "--port", "8787", "--no-access-log"]
