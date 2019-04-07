import configparser

CONFIG_PATH = "config/ini/options.ini"


config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError("No config in file: {}".format(CONFIG_PATH))


extensions = config["Bot"]["Extensions"].split()

token = config["Bot"]["Token"]

commandPrefixes = config["Bot"]["CommandPrefixes"].split()

status = config["Bot"]["Status"]
