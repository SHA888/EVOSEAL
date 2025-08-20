FROM python:3.10-slim
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn[standard]
COPY app.py /srv/app.py
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
