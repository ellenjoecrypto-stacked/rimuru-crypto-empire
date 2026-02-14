FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update &amp;&amp; apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    &amp;&amp; rm -rf /var/lib/apt/lists/*

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    &amp;&amp; tar -xzf ta-lib-0.4.0-src.tar.gz \
    &amp;&amp; cd ta-lib/ \
    &amp;&amp; ./configure --prefix=/usr \
    &amp;&amp; make \
    &amp;&amp; make install \
    &amp;&amp; cd .. \
    &amp;&amp; rm -rf ta-lib*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]