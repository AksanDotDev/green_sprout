import sys
from typing import Literal, List
from collections import deque
import discord
import tomlkit
import asyncio
import datetime
import zoneinfo
from discord import app_commands
from discord.ext import commands, tasks


config_path = sys.argv[1]

with open(config_path) as config:
    state = tomlkit.parse(config.read())


def write_back():
    with open(config_path, "w") as config:
        config.write(tomlkit.dumps(state))


intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    intents=intents
)


def user_tz(user_id):
    if user_id in state["users"]:
        return zoneinfo.ZoneInfo(state["users"][user_id])
    else:
        return None


available_timezones = zoneinfo.available_timezones()


@bot.tree.command()
@app_commands.rename(key="timezone")
async def settz(
    interaction: discord.Interaction,
    key: str
):
    if key not in available_timezones:
        await interaction.response.send_message(
            f"{key} is not a recognised IANA time zone.",
            ephemeral=True,
            delete_after=30
        )
    state["users"][str(interaction.user.id)] = key
    write_back()
    await interaction.response.send_message(
        f"Timezone updated to {zoneinfo.ZoneInfo(key)}.",
        ephemeral=True,
        delete_after=30
    )


@settz.autocomplete("key")
async def tz_key_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=key, value=key)
        for key in available_timezones if current.lower() in key.lower()
    ][:25]


format_type_str_to_char = {
    "relative": "R",
    "time": "t",
    "full": "F"
}

suggestions = deque()
SUGGESTION_RANGE = 1440
base = datetime.datetime.combine(
    datetime.date.today(),
    datetime.time(),
    None
)

for i in range(SUGGESTION_RANGE):
    suggestions.append(
        (
            base + datetime.timedelta(hours=i)
        ).isoformat(sep=" ", timespec="minutes")
    )


@tasks.loop(hours=1)
async def update_suggestions():
    leaving = datetime.datetime.fromisoformat(suggestions.popleft())
    suggestions.append(
        (
            leaving + datetime.timedelta(hours=SUGGESTION_RANGE)
        ).isoformat(sep=" ", timespec="minutes")
    )


@bot.tree.command()
@app_commands.rename(dt="datetime")
async def gettime(
    interaction: discord.Interaction,
    dt: str,
    type: Literal["relative", "time", "full"] = "time"
):
    try:
        parsed_dt = datetime.datetime.fromisoformat(dt)
    except ValueError:
        await interaction.response.send_message(
            f"{dt} is not an ISO Format datetime.",
            ephemeral=True,
            delete_after=30
        )
    else:
        tz = user_tz(str(interaction.user.id))
        print(tz)
        final_dt = parsed_dt.replace(tzinfo=tz).astimezone(tz=datetime.UTC)
        print(final_dt)
        await interaction.response.send_message(
            f"`<t:{int(final_dt.timestamp())}:{format_type_str_to_char[type]}>`",
            ephemeral=True,
            delete_after=30
        )


@bot.tree.command()
@app_commands.rename(dt="datetime")
async def posttime(
    interaction: discord.Interaction,
    dt: str,
    type: Literal["relative", "time", "full"] = "time"
):
    try:
        parsed_dt = datetime.datetime.fromisoformat(dt)
    except ValueError:
        await interaction.response.send_message(
            f"{dt} is not an ISO Format datetime.",
            ephemeral=True,
            delete_after=30
        )
    else:
        tz = user_tz(str(interaction.user.id))
        final_dt = parsed_dt.replace(tzinfo=tz).astimezone(tz=datetime.UTC)
        await interaction.response.send_message(
            f"<t:{int(final_dt.timestamp())}:{format_type_str_to_char[type]}>",
        )


@gettime.autocomplete("dt")
@posttime.autocomplete("dt")
async def dt_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    test_portions = current.split()
    return [
        app_commands.Choice(name=dt, value=dt)
        for dt in suggestions if all(
            ((portions in dt) for portions in test_portions)
        )
    ][:25]


@bot.event
async def on_ready():
    await bot.tree.sync()
    update_suggestions.start()


async def main():
    async with bot:
        await bot.start(state["discord"]["token"])


if __name__ == "__main__":
    asyncio.run(main())
