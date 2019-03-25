FROM gorialis/discord.py:3.7.1-stretch-rewrite-full
COPY . .
CMD ["python", "Referee.py"]
