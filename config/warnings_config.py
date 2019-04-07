import configparser

CONFIG_PATH = "config/ini/warnings.ini"


config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))


dyno_id = int(config["Warnings"]["DynoID"])

warning_lifetime = int(config["Warnings"]["WarningLifetime"])

warned_role_name = config["Warnings"]["WarnedRoleName"]

default_warned_color = (int(x) for x in config["Warnings"]["defaultWarnedColor"].split())


PG_Host = config["PostgreSQL"]["Host"]

PG_Database = config["PostgreSQL"]["Database"]

PG_User = config["PostgreSQL"]["User"]

PG_Password = config["PostgreSQL"]["Password"]
