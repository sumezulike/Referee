from typing import List, Dict

import discord

from config.config import Reputation as reputation_config
from models.reputation_models import Thank
from PIL import Image, ImageDraw, ImageFont
import logging
import io

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.animation import FuncAnimation, PillowWriter

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

def generate_graph(guild: discord.Guild, history: List[Thank]):
    fig, ax = plt.subplots()
    x = []

    users = {t.target_user_id: [] for t in history}
    for t in history:
        users[t.target_user_id].append(t)

    max_score = max(len(t) for u, t in users.items())

    start_day = history[0].timestamp.date()
    last_day = history[-1].timestamp.date()
    total_days = (last_day - start_day).days

    days: List[Dict[int, int]] = [{u: 0 for u in users} for _ in range(total_days+1)]

    for t in history:
        day = (t.timestamp.date() - start_day).days
        days[day][t.target_user_id] += 1

    graphs: Dict[int, List] = {u: [] for u in users}
    lines: Dict[int, Line2D] = {u: plt.plot([], [], 'g-')[0] for u in users}

    def init():
        ax.set_xlim(0, total_days)
        ax.set_ylim(0, max_score+1)

    user_scores = {u: 0 for u in users}

    def update(i):
        x.append(int(i))
        for user_id, score in days[int(i)].items():
            user_scores[user_id] += score
            graphs[user_id].append(user_scores[user_id])
            lines[user_id].set_data(x, graphs[user_id])

    ani = FuncAnimation(fig, update, np.linspace(0, total_days, total_days+1), init_func=init)

    writer = PillowWriter(fps=25)
    ani.save("graph.gif", writer=writer)

