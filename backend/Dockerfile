FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && groupadd -g 10001 arak && useradd -u 10001 -g 10001 -M arak && mkdir -p /data /media /app/staticfiles && chown -R 10001:10001 /data /media /app
COPY --chown=10001:10001 . .
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn","config.wsgi:application","--bind","0.0.0.0:8000","--workers","2","--threads","2","--timeout","30","--graceful-timeout","25"]
