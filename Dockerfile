FROM python:3.11

WORKDIR /app

COPY . /app

RUN pip install -U discord.py aiohttp python-dotenv flask

CMD ["python", "main.py"]
