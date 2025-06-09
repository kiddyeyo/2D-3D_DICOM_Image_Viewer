FROM python:3.12-slim

# Set working directory

WORKDIR /app

# Install system dependencies

RUN apt update && \
    apt install -y --no-install-recommends \
        build-essential \
        libgl1-mesa-glx \
        git && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code

COPY streamlit\_app.py ./

# Expose Streamlit port

EXPOSE 8501

# Run Streamlit

CMD streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=8501
