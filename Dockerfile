# 1) Base
FROM python:3.13-slim

# 2) System deps for pyodbc + MS ODBC 18
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg apt-transport-https ca-certificates \
    unixodbc unixodbc-dev gcc g++ \
 && rm -rf /var/lib/apt/lists/*

# Microsoft repo for msodbcsql18 (EULA auto-accept fix)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/ms.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ms.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/microsoft.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && rm -rf /var/lib/apt/lists/*

# 3) Workdir and Python deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copy code
COPY . .

# 5) Environment (FastAPI will read .env at runtime)
ENV PYTHONUNBUFFERED=1 \
    PORT=5000 \
    UVICORN_WORKERS=1

# 6) Expose port & default command
EXPOSE 5000
# If your main module is main.py with 'app' instance:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
