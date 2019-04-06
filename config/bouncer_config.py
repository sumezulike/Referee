import configparser

CONFIG_PATH = "config/ini/bouncer.ini"


config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))

first_channel_id = int(config["Bouncer"]["first_channel_id"])

second_channel_id = int(config["Bouncer"]["second_channel_id"])

newbie_role_name = config["Bouncer"]["newbie_role_name"]

accept_text = config["Bouncer"]["accept_text"]
