# ==========================================
# ETAPA 1: Construcción del frontend React
# ==========================================
FROM node:22-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==========================================
# ETAPA 2: Backend FastAPI + frontend
# ==========================================
FROM python:3.12-slim AS production

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

# Copiar el frontend compilado
COPY --from=frontend-build /frontend/dist ./frontend/dist

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
