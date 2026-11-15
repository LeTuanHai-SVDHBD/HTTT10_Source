FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home httt10 && mkdir -p /app/data/documents && chown -R httt10:httt10 /app/data && chmod 700 /app/data/documents
USER httt10
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--no-access-log","--proxy-headers","--forwarded-allow-ips=*"]
