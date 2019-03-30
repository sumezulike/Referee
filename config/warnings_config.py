import configparser

CONFIG_PATH = "config/warnings.ini"


config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))


dynoID = int(config["Warnings"]["DynoID"])

warningLifetime = int(config["Warnings"]["WarningLifetime"])

warnedRoleName = config["Warnings"]["WarnedRoleName"]


PG_Host = config["PostgreSQL"]["Host"]

PG_Database = config["PostgreSQL"]["Database"]

PG_User = config["PostgreSQL"]["User"]

PG_Password = config["PostgreSQL"]["Password"]
