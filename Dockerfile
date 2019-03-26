FROM discord.py:build0-3.7.2-stretch
COPY . .
CMD ["python", "Referee.py"]
