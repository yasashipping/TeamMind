# Yol B: model yok, konteyner hafif (~300 MB). Whisper/torch gerekmez.
FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Mevcut pipeline (repo kokundeki app/ klasoru) + backend
COPY app ./app
COPY backend/server.py backend/stt_google.py backend/stt_deepgram.py ./
ENV PORT=8080
CMD ["python", "server.py"]
