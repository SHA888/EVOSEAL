FROM python:3.10-slim
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic
COPY app.py /srv/app.py
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
