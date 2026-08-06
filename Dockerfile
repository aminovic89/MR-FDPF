FROM python:3.12-slim

WORKDIR /app

# Install dependencies only (not the project itself as a package): api/main.py
# locates the frontend/ dir relative to its own path assuming the backend/ and
# frontend/ directories stay siblings, exactly like local dev via PYTHONPATH.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "numpy>=1.26" "scipy>=1.11" "fastapi>=0.110" "uvicorn[standard]>=0.29" "pydantic>=2.6"

COPY backend ./backend
COPY frontend ./frontend

ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
