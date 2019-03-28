import configparser

CONFIG_FILE = "config/options.ini"


class Config:

    def __init__(self, path=CONFIG_FILE):

        self.config = configparser.ConfigParser()
        self.config.read(path)
        if not self.config.sections():
            raise FileNotFoundError("No config in file: {}".format(path))

    @property
    def extensions(self): return self.config["Bot"]["Extensions"].split()

    @property
    def dynoID(self): return self.config["Warnings"]["DynoID"]

    @property
    def description(self): return "Be warned, Referee is watching"

    @property
    def token(self): return self.config["Credentials"]["Token"]

    @property
    def warningLifetime(self): return int(self.config["Warnings"]["WarningLifetime"])

    @property
    def warnedRoleName(self): return self.config["Warnings"]["WarnedRoleName"]

    @property
    def commandPrefixes(self): return self.config["Chat"]["CommandPrefixes"].split()

    @property
    def PG_Host(self): return self.config["PostgreSQL"]["Host"]

    @property
    def PG_Database(self): return self.config["PostgreSQL"]["Database"]

    @property
    def PG_User(self): return self.config["PostgreSQL"]["User"]

    @property
    def PG_Password(self): return self.config["PostgreSQL"]["Password"]


config = Config()
