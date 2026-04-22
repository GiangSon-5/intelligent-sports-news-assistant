# Sử dụng base image chuẩn của Airflow tích hợp sẵn Python 3.11
FROM apache/airflow:2.8.1-python3.11

# Switch sang root để cài đặt OS dependencies cho Scrapy và WeasyPrint (PDF Export)
USER root
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libjpeg-dev \
    libopenjp2-7-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Chuyển về lại user airflow mặc định của image để đảm bảo Security
USER airflow

# Copy và cài đặt thư viện Python của dự án (bao gồm pandas, langchain, scrapy...)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
