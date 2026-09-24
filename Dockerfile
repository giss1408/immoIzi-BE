# Dockerfile

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

# Allows docker to cache installed dependencies between builds
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Mounts the application code to the image
COPY . /code
WORKDIR /code

RUN adduser --disabled-password --gecos "" django \
	&& chown -R django:django /code
USER django

EXPOSE 8000

CMD ["gunicorn", "immoizi.wsgi:application", "--chdir", "immoizi", "--bind", "0.0.0.0:8000"]