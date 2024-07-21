FROM python:3.9

WORKDIR /code

RUN mkdir downloads

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# COPY ./app /code/app


CMD ["fastapi", "run", "app/main.py", "--port", "8083"]
