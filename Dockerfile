FROM python:3.9-slim

# Install Chrome + dependencies
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    xvfb \
    pyautogui \
    python3-mss \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent.py .
COPY login.py .
COPY login_loop.py .

# Create directories for persistence
RUN mkdir -p /app/chrome_profiles /app/fresh_data /tmp

EXPOSE 7860

CMD ["python", "agent.py"]
