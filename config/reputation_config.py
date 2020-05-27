import configparser

CONFIG_PATH = "config/ini/reputation.ini"

config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))

PG_Host = config["PostgreSQL"]["Host"]

PG_Database = config["PostgreSQL"]["Database"]

PG_User = config["PostgreSQL"]["User"]

PG_Password = config["PostgreSQL"]["Password"]

cooldown = int(config["Reputation"]["DelayBetweenThanks"])

leaderboard_max_length = int(config["Reputation"]["LeaderboardLimit"])

max_mentions = int(config["Reputation"]["MaxMentions"])


fontsize = int(config["Draw"]["FontSize"])

default_fontcolor = config["Draw"]["FontColor"]
first_color = config["Draw"]["FirstColor"]
second_color = config["Draw"]["SecondColor"]
third_color = config["Draw"]["ThirdColor"]

font_colors = {
    1: first_color,
    2: second_color,
    3: third_color
}

background = config["Draw"]["Background"]
