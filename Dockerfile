FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY app/ ./app/

# Copy default sightings.csv (can be overridden by volume mount)
COPY sightings.csv ./data/sightings.csv

# Install dependencies with uv
RUN uv sync --frozen

# Create data directory for volume mounting
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Set default data file path (can be overridden)
ENV SIGHTINGS_FILE_PATH=/app/data/sightings.csv

# Run Streamlit
CMD ["uv", "run", "streamlit", "run", "app/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
