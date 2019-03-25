import configparser

CONFIG_FILE = "options.ini"


class Config:

    def __init__(self, path=CONFIG_FILE):
        self.config = configparser.ConfigParser()
        self.config.read(path)

    @property
    def dynoID(self): return self.config["Warnings"]["DynoID"]

    @property
    def description(self): return self.config["@property default"]["Description"]

    @property
    def token(self): return self.config["Credentials"]["Token"]

    @property
    def warningLifetime(self): return self.config["Warnings"]["WarningLifetime"]

    @property
    def warnedRoleName(self): return self.config["Warnings"]["WarnedRoleName"]

    @property
    def debugLevel(self): return self.config["Chat"]["DebugLevel"]

    @property
    def commandPrefixes(self): return self.config["Chat"]["CommandPrefix"].split()

    @property
    def PG_Host(self): return self.config["PostgreSQL"]["Host"]

    @property
    def PG_Database(self): return self.config["PostgreSQL"]["Database"]

    @property
    def PG_User(self): return self.config["PostgreSQL"]["User"]

    @property
    def PG_Password(self): return self.config["PostgreSQL"]["Password"]
