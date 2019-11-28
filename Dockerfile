FROM gorialis/discord.py:3.8.0-buster-master-full
COPY . .
CMD ["python", "Referee.py"]
