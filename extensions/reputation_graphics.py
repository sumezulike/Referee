from typing import List, Dict

import discord
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from config.config import Reputation as reputation_config
from models.reputation_models import Thank
from PIL import Image, ImageDraw, ImageFont
import logging
import io

import matplotlib.pyplot as plt

logger = logging.getLogger("Referee")


async def draw_scoreboard(leaderboard: list, guild: discord.Guild, highlight=None):
    width = reputation_config.fontsize * 13
    row_height = reputation_config.fontsize + reputation_config.fontsize // 2
    height = (len(leaderboard) + 1) * row_height

    bg = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    text = Image.new("RGBA", bg.size, (255, 255, 255, 0))

    pics = Image.new("RGBA", bg.size, (255, 255, 255, 0))
    fnt = ImageFont.truetype('coolvetica.ttf', reputation_config.fontsize)
    text_draw = ImageDraw.Draw(text)

    rank_x = reputation_config.fontsize
    name_x = 2 * reputation_config.fontsize
    point_x = width - reputation_config.fontsize

    line_x = name_x
    max_line_width = (point_x - name_x)

    i = 0

    for row in leaderboard:
        rank, member_id, score = row["rank"], row["user_id"], row["score"]
        member = guild.get_member(member_id)
        if not member:
            logger.error(f"No member with user_id {member_id}")
            continue

        row_y = i * row_height + (reputation_config.fontsize // 2)
        line_y = row_y + int(reputation_config.fontsize * 1.2)

        row_color = reputation_config.font_colors.get(rank, reputation_config.default_fontcolor)

        if highlight:
            if (highlight.get("member_id", None) == member_id or
                    highlight.get("rank", None) == rank or
                    highlight.get("score", None) == score or
                    highlight.get("row", None) == i):
                row_color = reputation_config.highlight_color

        w, h = text_draw.textsize(f"{rank}", font=fnt)
        text_draw.text((rank_x - w, row_y), f"{rank}", font=fnt,
                       fill=(255, 255, 255, 50))
        name = member.display_name
        w, h = text_draw.textsize(f"{name}", font=fnt)
        score_w, _ = text_draw.textsize(f"{score}", font=fnt)
        while name_x + w >= point_x - score_w:
            name = name[:-1]
            w, h = text_draw.textsize(f"{name}...", font=fnt)
        text_draw.text((name_x, row_y), f"{name}" if name == member.display_name else f"{name}...", font=fnt,
                       fill=row_color)

        w, h = text_draw.textsize(f"{score}", font=fnt)
        text_draw.text((point_x - w, row_y), f"{score}", font=fnt,
                       fill=row_color)

        text_draw.line([line_x, line_y,
                        line_x + int(max_line_width * score / leaderboard[0]["score"]), line_y],
                       fill=row_color, width=2)

        i += 1

    out = Image.alpha_composite(Image.alpha_composite(bg, text), pics)
    tmp_img = io.BytesIO()
    out.save(tmp_img, format="png")
    tmp_img.seek(0)
    return tmp_img


async def generate_graph(guild: discord.Guild, history: List[Thank], format="gif") -> str:
    fig: Figure
    ax: Axes
    fig, ax = plt.subplots()
    x = []

    # all thanks of which the giver is still in the server
    history = [t for t in history if guild.get_member(t.target_user_id)]

    thanks_by_user_id = {t.target_user_id: [] for t in history}
    for t in history:
        thanks_by_user_id[t.target_user_id].append(t)

    most_thanks = max(len(t) for _, t in thanks_by_user_id.items())

    start_day = history[0].timestamp.date()
    last_day = history[-1].timestamp.date()
    # + 1, because (easy example) if the only day is today, "today - today = 0", but we actually have 1 total day
    total_days = (last_day - start_day).days + 1

    # cumulative!
    # User Id -> Number of thanks indexed by day
    thank_amount_per_user_and_day: Dict[int, List[int]] = {uid: [0 for d in range(total_days)] for uid in thanks_by_user_id.keys()}

    print(total_days)

    for t in history:
        day = (t.timestamp.date() - start_day).days
        thank_amount_per_user_and_day[t.target_user_id][day] += 1
        print(day, t.target_user_id)

    for user, user_thanks_per_day in thank_amount_per_user_and_day.items():
        for day, thanks_on_day in enumerate(user_thanks_per_day):
            if day != 0:
                # https://stackoverflow.com/a/4082739
                # modifying entries of the list while enumerating seems to be safe here, since we're only doing it on
                # already-seen ones.
                user_thanks_per_day[day] = user_thanks_per_day[day - 1] + thanks_on_day

        member = guild.get_member(user)
        # randomizing colors based on user id should be fine?
        ax.plot(user_thanks_per_day, f"xkcd:{COLORS[user % len(COLORS)]}", label=f"{member.name}#{member.discriminator}")

    ax.set_ylabel("Amount of Thanks")
    ax.set_xlabel("Days")
    ax.legend()
    fig.savefig("graph.png")

    return "graph.png"


COLORS = """cloudy blue;dark pastel green;dust;electric lime;fresh green;light eggplant;nasty green;really light blue;tea;warm purple;yellowish tan;cement;dark grass green;dusty teal;grey teal;macaroni and cheese;pinkish tan;spruce;strong blue;toxic green;windows blue;blue blue;blue with a hint of purple;booger;bright sea green;dark green blue;deep turquoise;green teal;strong pink;bland;deep aqua;lavender pink;light moss green;light seafoam green;olive yellow;pig pink;deep lilac;desert;dusty lavender;purpley grey;purply;candy pink;light pastel green;boring green;kiwi green;light grey green;orange pink;tea green;very light brown;egg shell;eggplant purple;powder pink;reddish grey;baby shit brown;liliac;stormy blue;ugly brown;custard;darkish pink;deep brown;greenish beige;manilla;off blue;battleship grey;browny green;bruise;kelley green;sickly yellow;sunny yellow;azul;darkgreen;green/yellow;lichen;light light green;pale gold;sun yellow;tan green;burple;butterscotch;toupe;dark cream;indian red;light lavendar;poison green;baby puke green;bright yellow green;charcoal grey;squash;cinnamon;light pea green;radioactive green;raw sienna;baby purple;cocoa;light royal blue;orangeish;rust brown;sand brown;swamp;tealish green;burnt siena;camo;dusk blue;fern;old rose;pale light green;peachy pink;rosy pink;light bluish green;light bright green;light neon green;light seafoam;tiffany blue;washed out green;browny orange;nice blue;sapphire;greyish teal;orangey yellow;parchment;straw;very dark brown;terracota;ugly blue;clear blue;creme;foam green;grey/green;light gold;seafoam blue;topaz;violet pink;wintergreen;yellow tan;dark fuchsia;indigo blue;light yellowish green;pale magenta;rich purple;sunflower yellow;green/blue;leather;racing green;vivid purple;dark royal blue;hazel;muted pink;booger green;canary;cool grey;dark taupe;darkish purple;true green;coral pink;dark sage;dark slate blue;flat blue;mushroom;rich blue;dirty purple;greenblue;icky green;light khaki;warm blue;dark hot pink;deep sea blue;carmine;dark yellow green;pale peach;plum purple;golden rod;neon red;old pink;very pale blue;blood orange;grapefruit;sand yellow;clay brown;dark blue grey;flat green;light green blue;warm pink;dodger blue;gross green;ice;metallic blue;pale salmon;sap green;algae;bluey grey;greeny grey;highlighter green;light light blue;light mint;raw umber;vivid blue;deep lavender;dull teal;light greenish blue;mud green;pinky;red wine;shit green;tan brown;darkblue;rosa;lipstick;pale mauve;claret;dandelion;orangered;poop green;ruby;dark;greenish turquoise;pastel red;piss yellow;bright cyan;dark coral;algae green;darkish red;reddy brown;blush pink;camouflage green;lawn green;putty;vibrant blue;dark sand;purple/blue;saffron;twilight;warm brown;bluegrey;bubble gum pink;duck egg blue;greenish cyan;petrol;royal;butter;dusty orange;off yellow;pale olive green;orangish;leaf;light blue grey;dried blood;lightish purple;rusty red;lavender blue;light grass green;light mint green;sunflower;velvet;brick orange;lightish red;pure blue;twilight blue;violet red;yellowy brown;carnation;muddy yellow;dark seafoam green;deep rose;dusty red;grey/blue;lemon lime;purple/pink;brown yellow;purple brown;wisteria;banana yellow;lipstick red;water blue;brown grey;vibrant purple;baby green;barf green;eggshell blue;sandy yellow;cool green;pale;blue/grey;hot magenta;greyblue;purpley;baby shit green;brownish pink;dark aquamarine;diarrhea;light mustard;pale sky blue;turtle green;bright olive;dark grey blue;greeny brown;lemon green;light periwinkle;seaweed green;sunshine yellow;ugly purple;medium pink;puke brown;very light pink;viridian;bile;faded yellow;very pale green;vibrant green;bright lime;spearmint;light aquamarine;light sage;yellowgreen;baby poo;dark seafoam;deep teal;heather;rust orange;dirty blue;fern green;bright lilac;weird green;peacock blue;avocado green;faded orange;grape purple;hot green;lime yellow;mango;shamrock;bubblegum;purplish brown;vomit yellow;pale cyan;key lime;tomato red;lightgreen;merlot;night blue;purpleish pink;apple;baby poop green;green apple;heliotrope;yellow/green;almost black;cool blue;leafy green;mustard brown;dusk;dull brown;frog green;vivid green;bright light green;fluro green;kiwi;seaweed;navy green;ultramarine blue;iris;pastel orange;yellowish orange;perrywinkle;tealish;dark plum;pear;pinkish orange;midnight purple;light urple;dark mint;greenish tan;light burgundy;turquoise blue;ugly pink;sandy;electric pink;muted purple;mid green;greyish;neon yellow;banana;carnation pink;tomato;sea;muddy brown;turquoise green;buff;fawn;muted blue;pale rose;dark mint green;amethyst;blue/green;chestnut;sick green;pea;rusty orange;stone;rose red;pale aqua;deep orange;earth;mossy green;grassy green;pale lime green;light grey blue;pale grey;asparagus;blueberry;purple red;pale lime;greenish teal;caramel;deep magenta;light peach;milk chocolate;ocher;off green;purply pink;lightblue;dusky blue;golden;light beige;butter yellow;dusky purple;french blue;ugly yellow;greeny yellow;orangish red;shamrock green;orangish brown;tree green;deep violet;gunmetal;blue/purple;cherry;sandy brown;warm grey;dark indigo;midnight;bluey green;grey pink;soft purple;blood;brown red;medium grey;berry;poo;purpley pink;light salmon;snot;easter purple;light yellow green;dark navy blue;drab;light rose;rouge;purplish red;slime green;baby poop;irish green;pink/purple;dark navy;greeny blue;light plum;pinkish grey;dirty orange;rust red;pale lilac;orangey red;primary blue;kermit green;brownish purple;murky green;wheat;very dark purple;bottle green;watermelon;deep sky blue;fire engine red;yellow ochre;pumpkin orange;pale olive;light lilac;lightish green;carolina blue;mulberry;shocking pink;auburn;bright lime green;celadon;pinkish brown;poo brown;bright sky blue;celery;dirt brown;strawberry;dark lime;copper;medium brown;muted green;robin's egg;bright aqua;bright lavender;ivory;very light purple;light navy;pink red;olive brown;poop brown;mustard green;ocean green;very dark blue;dusty green;light navy blue;minty green;adobe;barney;jade green;bright light blue;light lime;dark khaki;orange yellow;ocre;maize;faded pink;british racing green;sandstone;mud brown;light sea green;robin egg blue;aqua marine;dark sea green;soft pink;orangey brown;cherry red;burnt yellow;brownish grey;camel;purplish grey;marine;greyish pink;pale turquoise;pastel yellow;bluey purple;canary yellow;faded red;sepia;coffee;bright magenta;mocha;ecru;purpleish;cranberry;darkish green;brown orange;dusky rose;melon;sickly green;silver;purply blue;purpleish blue;hospital green;shit brown;mid blue;amber;easter green;soft blue;cerulean blue;golden brown;bright turquoise;red pink;red purple;greyish brown;vermillion;russet;steel grey;lighter purple;bright violet;prussian blue;slate green;dirty pink;dark blue green;pine;yellowy green;dark gold;bluish;darkish blue;dull red;pinky red;bronze;pale teal;military green;barbie pink;bubblegum pink;pea soup green;dark mustard;shit;medium purple;very dark green;dirt;dusky pink;red violet;lemon yellow;pistachio;dull yellow;dark lime green;denim blue;teal blue;lightish blue;purpley blue;light indigo;swamp green;brown green;dark maroon;hot purple;dark forest green;faded blue;drab green;light lime green;snot green;yellowish;light blue green;bordeaux;light mauve;ocean;marigold;muddy green;dull orange;steel;electric purple;fluorescent green;yellowish brown;blush;soft green;bright orange;lemon;purple grey;acid green;pale lavender;violet blue;light forest green;burnt red;khaki green;cerise;faded purple;apricot;dark olive green;grey brown;green grey;true blue;pale violet;periwinkle blue;light sky blue;blurple;green brown;bluegreen;bright teal;brownish yellow;pea soup;forest;barney purple;ultramarine;purplish;puke yellow;bluish grey;dark periwinkle;dark lilac;reddish;light maroon;dusty purple;terra cotta;avocado;marine blue;teal green;slate grey;lighter green;electric green;dusty blue;golden yellow;bright yellow;light lavender;umber;poop;dark peach;jungle green;eggshell;denim;yellow brown;dull purple;chocolate brown;wine red;neon blue;dirty green;light tan;ice blue;cadet blue;dark mauve;very light blue;grey purple;pastel pink;very light green;dark sky blue;evergreen;dull pink;aubergine;mahogany;reddish orange;deep green;vomit green;purple pink;dusty pink;faded green;camo green;pinky purple;pink purple;brownish red;dark rose;mud;brownish;emerald green;pale brown;dull blue;burnt umber;medium green;clay;light aqua;light olive green;brownish orange;dark aqua;purplish pink;dark salmon;greenish grey;jade;ugly green;dark beige;emerald;pale red;light magenta;sky;light cyan;yellow orange;reddish purple;reddish pink;orchid;dirty yellow;orange red;deep red;orange brown;cobalt blue;neon pink;rose pink;greyish purple;raspberry;aqua green;salmon pink;tangerine;brownish green;red brown;greenish brown;pumpkin;pine green;charcoal;baby pink;cornflower;blue violet;chocolate;greyish green;scarlet;green yellow;dark olive;sienna;pastel purple;terracotta;aqua blue;sage green;blood red;deep pink;grass;moss;pastel blue;bluish green;green blue;dark tan;greenish blue;pale orange;vomit;forrest green;dark lavender;dark violet;purple blue;dark cyan;olive drab;pinkish;cobalt;neon purple;light turquoise;apple green;dull green;wine;powder blue;off white;electric blue;dark turquoise;blue purple;azure;bright red;pinkish red;cornflower blue;light olive;grape;greyish blue;purplish blue;yellowish green;greenish yellow;medium blue;dusty rose;light violet;midnight blue;bluish purple;red orange;dark magenta;greenish;ocean blue;coral;cream;reddish brown;burnt sienna;brick;sage;grey green;white;robin's egg blue;moss green;steel blue;eggplant;light yellow;leaf green;light grey;puke;pinkish purple;sea blue;pale purple;slate blue;blue grey;hunter green;fuchsia;crimson;pale yellow;ochre;mustard yellow;light red;cerulean;pale pink;deep blue;rust;light teal;slate;goldenrod;dark yellow;dark grey;army green;grey blue;seafoam;puce;spring green;dark orange;sand;pastel green;mint;light orange;bright pink;chartreuse;deep purple;dark brown;taupe;pea green;puke green;kelly green;seafoam green;blue green;khaki;burgundy;dark teal;brick red;royal purple;plum;mint green;gold;baby blue;yellow green;bright purple;dark red;pale blue;grass green;navy;aquamarine;burnt orange;neon green;bright blue;rose;light pink;mustard;indigo;lime;sea green;periwinkle;dark pink;olive green;peach;pale green;light brown;hot pink;black;lilac;navy blue;royal blue;beige;salmon;olive;maroon;bright green;dark purple;mauve;forest green;aqua;cyan;tan;dark blue;lavender;turquoise;dark green;violet;light purple;lime green;grey;sky blue;yellow;magenta;light green;orange;teal;light blue;red;brown;pink;blue;green;purple""".split(
    ";")
