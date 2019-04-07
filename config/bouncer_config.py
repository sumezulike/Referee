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

welcome_message = """Here you can find help on programming topics, discuss your ideas, share what you're working on, and more.
Join the discussion in <#222721769696526337> or check out some of the popular channels at the bottom.

**IF YOU NEED HELP** with something (**remember:** **be** ***specific***), 
go to the appropriate channel or <#279954937855606785>

<#227521002056187904> - <#227520285304291329> - <#484991156447477760>
<#349848732369551360> - <#285543876209410048> - <#227519949235552256>
<#279972460806537217>
<#479598294084091904> - <#401819392431620106>
"""
