import json
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("matinbot")

SERVERS_FILE = Path(__file__).with_name("servers.json")


def load_registered_servers() -> dict[str, dict[str, str]]:
    if not SERVERS_FILE.exists():
        return {}

    with SERVERS_FILE.open(encoding="utf-8") as file:
        servers = json.load(file)

    if not isinstance(servers, dict) or any(
        not isinstance(server_id, str)
        or not isinstance(server, dict)
        or not isinstance(server.get("name"), str)
        or not isinstance(server.get("invite"), str)
        for server_id, server in servers.items()
    ):
        raise ValueError(f"{SERVERS_FILE} must contain a server-ID-to-server-object mapping")

    return servers


def save_registered_servers(servers: dict[str, dict[str, str]]) -> None:
    temporary_file = SERVERS_FILE.with_suffix(".json.tmp")
    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(servers, file, indent=2)
            file.write("\n")
        temporary_file.replace(SERVERS_FILE)
    finally:
        if temporary_file.exists():
            temporary_file.unlink()


registered_servers = load_registered_servers()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
    await ctx.send("Pong")


@bot.command(name="registerserver")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def registerserver(ctx: commands.Context) -> None:
    guild = ctx.guild
    if guild is None:
        return

    bot_member = guild.me
    if bot_member is None:
        await ctx.send("I couldn't find my bot account in this server.")
        return

    channels = list(guild.text_channels)
    if guild.system_channel in channels:
        channels.remove(guild.system_channel)
        channels.insert(0, guild.system_channel)

    invite_channel = next(
        (
            channel
            for channel in channels
            if channel.permissions_for(bot_member).create_instant_invite
        ),
        None,
    )
    if invite_channel is None:
        await ctx.send(
            "I can't create an invite link in this server. "
            "Please grant me the Create Invite permission in a text channel."
        )
        return

    invite = await invite_channel.create_invite(
        max_age=0,
        max_uses=0,
        reason=f"Server registered by {ctx.author} ({ctx.author.id})",
    )
    registered_servers[str(guild.id)] = {
        "name": guild.name,
        "invite": invite.url,
    }
    save_registered_servers(registered_servers)
    await ctx.send(f"Registered **{guild.name}**. Invite link: {invite.url}")


@bot.command(name="join")
async def join(ctx: commands.Context, server_id: str) -> None:
    if not server_id.isdecimal():
        await ctx.send("Please provide a valid server ID.")
        return

    server = registered_servers.get(server_id)
    if server is None:
        await ctx.send("That server isn't registered.")
        return

    await ctx.send(f"Invite to **{server['name']}**: {server['invite']}")


@bot.command(name="servers")
async def servers(ctx: commands.Context) -> None:
    await ctx.send(f"Registered servers: {len(registered_servers)}")


@registerserver.error
async def registerserver_error(
    ctx: commands.Context, error: commands.CommandError
) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Only server administrators can register a server.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can only be used in a server.")
    else:
        logger.error(
            "Failed to register server",
            exc_info=(type(error), error, error.__traceback__),
        )
        await ctx.send("I couldn't register this server. Please try again later.")


@bot.event
async def on_command_error(
    ctx: commands.Context, error: commands.CommandError
) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Usage: `!{ctx.command} <server_id>`")
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can only be used in a server.")
        return

    logger.error(
        "Command failed",
        exc_info=(type(error), error, error.__traceback__),
    )
    await ctx.send("Something went wrong while running that command.")


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set the DISCORD_TOKEN environment variable before starting MatinBot.")
    bot.run(token)


if __name__ == "__main__":
    main()
