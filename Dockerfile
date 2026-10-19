FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY . .

# Set environment
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "dashboard_server.py"]
