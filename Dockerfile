FROM python:3.13

WORKDIR /src

# done first so we can cache dependencies between code changes
COPY Pipfile Pipfile.lock ./
RUN pip install -U pipenv
RUN pipenv install --system

RUN apt-get update && apt-get install -y nginx && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY etc/nginx.conf /etc/nginx/sites-available/default

COPY . .

RUN bash ./plugin_install

RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Command to run
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
