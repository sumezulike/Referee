import configparser

CONFIG_PATH = "config/modmail.ini"


config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))


anonymize_responses = config["ModMail"]["AnonymizeResponses"].lower() in ["true", "yes", "y", "1", ]

mod_channel_id = int(config["ModMail"]["ModChannelID"])


PG_Host = config["PostgreSQL"]["Host"]

PG_Database = config["PostgreSQL"]["Database"]

PG_User = config["PostgreSQL"]["User"]

PG_Password = config["PostgreSQL"]["Password"]
