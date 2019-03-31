import configparser

CONFIG_PATH = "config/ranks.ini"


config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))

ranks_channel_id = int(config["Ranks"]["RanksChannelID"])

cooldown_count = int(config["Ranks"]["CooldownCount"])

cooldown_time = int(config["Ranks"]["CooldownTime"])

rank_count_limit = int(config["Ranks"]["RankCountLimit"])


PG_Host = config["PostgreSQL"]["Host"]

PG_Database = config["PostgreSQL"]["Database"]

PG_User = config["PostgreSQL"]["User"]

PG_Password = config["PostgreSQL"]["Password"]
