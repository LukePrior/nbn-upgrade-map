FROM python:3-alpine

RUN apk add libpq-dev gcc musl-dev

WORKDIR /app
ADD code ./
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "./main.py" ]
