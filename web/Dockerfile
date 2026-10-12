# Überzeit -- Server-Version des Überzeit-Rechners. Gebaut aus der Repo-Wurzel (compose.yml),
# weil die Rechenregeln (kern.py, models.py) mit der Desktop-App geteilt werden.
FROM python:3.13-slim

WORKDIR /app
COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kern.py models.py /
COPY web/app.py web/auswertung.py web/austausch.py web/laender.py web/oidc.py web/speicher.py web/sicherung.py web/gunicorn.conf.py ./
COPY web/templates/ ./templates/
COPY web/static/ ./static/

# Nicht als root. HOME=/tmp: gunicorn legt dort seinen Steuer-Socket an.
USER 1001
ENV DATENBANK=/daten/ueberzeit.db \
    HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin

EXPOSE 5026
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:erstelle_app()"]
