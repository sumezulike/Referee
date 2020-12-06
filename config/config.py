import configparser

CONFIG_PATH = "config/options.ini"

config = configparser.ConfigParser()
config.read(CONFIG_PATH)
if not config.sections():
    raise FileNotFoundError(f"No config in file: {CONFIG_PATH}")

class __T:
    def __init__(self):
        self.long = float(config["Bot"]["TimeoutLong"])
        self.mid = float(config["Bot"]["TimeoutMid"])
        self.short = float(config["Bot"]["TimeoutShort"])
Timeouts = __T()

class Bot:
    extensions = config["Bot"]["Extensions"].split()
    token = config["Bot"]["Token"]
    commandPrefixes = config["Bot"]["CommandPrefixes"].split()
    status = config["Bot"]["Status"]
    logging_level = int(config["Bot"]["LoggingLevel"])


class Misc:
    bitly_token = config["Misc"]["BitlyToken"]


class PostGres:
    PG_Host = config["PostgreSQL"]["Host"]
    PG_Database = config["PostgreSQL"]["Database"]
    PG_User = config["PostgreSQL"]["User"]
    PG_Password = config["PostgreSQL"]["Password"]


class Bouncer:
    first_channel_id = int(config["Bouncer"]["first_channel_id"])
    second_channel_id = int(config["Bouncer"]["second_channel_id"])
    newbie_role_name = config["Bouncer"]["newbie_role_name"]
    accept_text = config["Bouncer"]["accept_text"]
    welcome_message = """Here you can find help on programming topics, discuss your ideas, share what you're working on, and more.
    Join the discussion in <#222721769696526337> or check out some of the popular channels at the bottom.

    **IF YOU NEED HELP** with something (**remember:** **be** ***specific***), 
    go to the appropriate channel or <#279954937855606785>

    <#227521002056187904> - <#227520285304291329> - <#484991156447477760>
    <#349848732369551360> - <#285543876209410048> - <#227519949235552256>
    <#279972460806537217>
    <#479598294084091904> - <#401819392431620106>
    """


class ModMail:
    anonymize_responses = config["ModMail"]["AnonymizeResponses"].lower() in (
        'yes', 'y', 'true', 't', '1', 'enable', 'on')
    mod_channel_id = int(config["ModMail"]["ModChannelID"])
    cooldown = int(config["ModMail"]["Cooldown"])


class Ranks:
    ranks_channel_id = int(config["Ranks"]["RanksChannelID"])
    cooldown_count = int(config["Ranks"]["CooldownCount"])
    cooldown_time = int(config["Ranks"]["CooldownTime"])
    rank_count_limit = int(config["Ranks"]["RankCountLimit"])


class Reputation:
    cooldown = int(config["Reputation"]["DelayBetweenThanks"])
    leaderboard_max_length = int(config["Reputation"]["LeaderboardLimit"])
    max_mentions = int(config["Reputation"]["MaxMentions"])
    thanked_role = int(config["Reputation"]["ThankedRole"])
    thanked_role_threshold = int(config["Reputation"]["ThankedRoleThreshold"])
    fontsize = int(config["Reputation"]["FontSize"])
    default_fontcolor = config["Reputation"]["FontColor"]
    first_color = config["Reputation"]["FirstColor"]
    second_color = config["Reputation"]["SecondColor"]
    third_color = config["Reputation"]["ThirdColor"]
    font_colors = {
        1: first_color,
        2: second_color,
        3: third_color
    }
    highlight_color = config["Reputation"]["HighlightColor"]
    background = config["Reputation"]["Background"]


class Warnings:
    dyno_id = int(config["Warnings"]["DynoID"])
    warning_lifetime = int(config["Warnings"]["WarningLifetime"])
    warned_role_name = config["Warnings"]["WarnedRoleName"]
    default_warned_color = (int(x) for x in config["Warnings"]["defaultWarnedColor"].split())


class Rolegroups:
    channel_id = int(config["Rolegroups"]["RolegroupsChannelID"])
    cooldown_count = int(config["Rolegroups"]["CooldownCount"])
    cooldown_time = int(config["Rolegroups"]["CooldownTime"])
    role_count_limit = int(config["Rolegroups"]["RoleCountLimit"])
