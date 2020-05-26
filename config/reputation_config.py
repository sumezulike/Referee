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

Leader_Limit = int(config["Reputation"]["LeaderboardLimit"])

max_mentions = int(config["Reputation"]["MaxMentions"])


fontsize = int(config["Draw"]["FontSize"])

default_fontcolor = config["Draw"]["FontColor"]
firstcolor = config["Draw"]["FirstColor"]
secondcolor = config["Draw"]["SecondColor"]
thirdcolor = config["Draw"]["ThirdColor"]

fontcolors = {
    1: firstcolor,
    2: secondcolor,
    3: thirdcolor
}

background = config["Draw"]["Background"]
