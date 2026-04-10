# Mangrove Studio — Docker-primary distribution
# TODO 8: Multi-stage build, multi-arch (amd64, arm64), target <500MB

FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

EXPOSE 3000
CMD ["mangrove", "studio", "--port", "3000"]
