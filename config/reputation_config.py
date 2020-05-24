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

RepDelay = int(config["Reputation"]["DelayBetweenThanks"])

Debug = config["Reputation"]["Debug"].lower() in ('yes', 'y', 'true', 't', '1', 'enable', 'on')

LB_Limit = int(config["Reputation"]["Limit"])
