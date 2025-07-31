import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import timedelta, datetime
from dotenv import load_dotenv  # NEW

# === CONFIG ===
load_dotenv()  # NEW
TOKEN = os.getenv("DISCORD_TOKEN")  # NEW

if TOKEN is None:
    print("? Error: DISCORD_TOKEN not found in .env")
    exit()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents)
tree = bot.tree

WARN_DATA_FILE = "warns.json"
MODLOG_DATA_FILE = "modlog.json"

# Load or init warns data
if os.path.exists(WARN_DATA_FILE):
    with open(WARN_DATA_FILE, "r") as f:
        warns = json.load(f)
else:
    warns = {}

# Load or init modlog channel data (guild_id -> channel_id)
if os.path.exists(MODLOG_DATA_FILE):
    with open(MODLOG_DATA_FILE, "r") as f:
        modlog_channels = json.load(f)
else:
    modlog_channels = {}

# Mention intro cooldown tracking (user_id -> datetime)
mention_intro_cooldowns = {}
INTRO_COOLDOWN_HOURS = 6

def save_warns():
    with open(WARN_DATA_FILE, "w") as f:
        json.dump(warns, f)

def save_modlogs():
    with open(MODLOG_DATA_FILE, "w") as f:
        json.dump(modlog_channels, f)

def build_embed(title, description, color=discord.Color.orange()):
    return discord.Embed(title=title, description=description, color=color)

async def log_mod_action(guild: discord.Guild, embed: discord.Embed):
    channel_id = modlog_channels.get(str(guild.id))
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(embed=embed)
        except:
            pass

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

def get_member_by_name_or_mention(ctx, name: str):
    # Check mention format
    if name.startswith("<@") and name.endswith(">"):
        member_id = name.strip("<@!>")  # remove <@ and >
        return ctx.guild.get_member(int(member_id))
    # Check by username or nickname (case insensitive)
    name_lower = name.lower()
    for member in ctx.guild.members:
        if member.name.lower() == name_lower or (member.nick and member.nick.lower() == name_lower):
            return member
    return None

# ---------- PREFIX COMMANDS ----------

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member_name: str, *, reason: str = "No reason provided"):
    member = get_member_by_name_or_mention(ctx, member_name)
    if not member:
        await ctx.send("?? Member not found.")
        return

    warns[str(member.id)] = warns.get(str(member.id), 0) + 1
    save_warns()

    try:
        await member.timeout(timedelta(minutes=30), reason=reason)
    except discord.Forbidden:
        await ctx.send("? I don't have permission to timeout that member.")
        return

    embed = build_embed(
        "User Warned",
        f"**User:** {member.mention}\n"
        f"**Total Warns:** {warns[str(member.id)]}\n"
        f"**30-minute timeout applied**\n"
        f"**Reason:** {reason}",
        color=discord.Color.gold(),
    )
    await ctx.send(embed=embed)
    await log_mod_action(ctx.guild, embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member_name: str, *, reason: str = "No reason provided"):
    member = get_member_by_name_or_mention(ctx, member_name)
    if not member:
        await ctx.send("?? Member not found.")
        return
    try:
        await member.kick(reason=reason)
    except discord.Forbidden:
        await ctx.send("? I don't have permission to kick that member.")
        return
    embed = build_embed(
        "User Kicked",
        f"**User:** {member.mention}\n"
        f"**Reason:** {reason}",
        color=discord.Color.red(),
    )
    await ctx.send(embed=embed)
    await log_mod_action(ctx.guild, embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member_name: str, *, reason: str = "No reason provided"):
    member = get_member_by_name_or_mention(ctx, member_name)
    if not member:
        await ctx.send("?? Member not found.")
        return
    try:
        await member.ban(reason=reason)
    except discord.Forbidden:
        await ctx.send("? I don't have permission to ban that member.")
        return
    embed = build_embed(
        "User Banned",
        f"**User:** {member.mention}\n"
        f"**Reason:** {reason}",
        color=discord.Color.dark_red(),
    )
    await ctx.send(embed=embed)
    await log_mod_action(ctx.guild, embed)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member_name: str, minutes: int):
    member = get_member_by_name_or_mention(ctx, member_name)
    if not member:
        await ctx.send("?? Member not found.")
        return
    try:
        await member.timeout(timedelta(minutes=minutes))
    except discord.Forbidden:
        await ctx.send("? I don't have permission to timeout that member.")
        return
    embed = build_embed(
        "User Timed Out",
        f"**User:** {member.mention}\n"
        f"**Duration:** {minutes} minutes",
        color=discord.Color.blue(),
    )
    await ctx.send(embed=embed)
    await log_mod_action(ctx.guild, embed)

# ---------- SLASH COMMANDS ----------

@tree.command(name="warn", description="Warn a user and apply a 30-min timeout")
@app_commands.describe(user="User to warn", reason="Reason for warning")
@commands.has_permissions(moderate_members=True)
async def warn_slash(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    warns[str(user.id)] = warns.get(str(user.id), 0) + 1
    save_warns()

    try:
        await user.timeout(timedelta(minutes=30), reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message("? I don't have permission to timeout that member.", ephemeral=True)
        return

    embed = build_embed(
        "User Warned",
        f"**User:** {user.mention}\n"
        f"**Total Warns:** {warns[str(user.id)]}\n"
        f"**30-minute timeout applied**\n"
        f"**Reason:** {reason}",
        color=discord.Color.gold(),
    )
    await interaction.response.send_message(embed=embed)
    await log_mod_action(interaction.guild, embed)

@tree.command(name="kick", description="Kick a user")
@app_commands.describe(user="User to kick", reason="Reason for kicking")
@commands.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    try:
        await user.kick(reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message("? I don't have permission to kick that member.", ephemeral=True)
        return

    embed = build_embed(
        "User Kicked",
        f"**User:** {user.mention}\n"
        f"**Reason:** {reason}",
        color=discord.Color.red(),
    )
    await interaction.response.send_message(embed=embed)
    await log_mod_action(interaction.guild, embed)

@tree.command(name="ban", description="Ban a user")
@app_commands.describe(user="User to ban", reason="Reason for banning")
@commands.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    try:
        await user.ban(reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message("? I don't have permission to ban that member.", ephemeral=True)
        return

    embed = build_embed(
        "User Banned",
        f"**User:** {user.mention}\n"
        f"**Reason:** {reason}",
        color=discord.Color.dark_red(),
    )
    await interaction.response.send_message(embed=embed)
    await log_mod_action(interaction.guild, embed)

@tree.command(name="timeout", description="Timeout a user")
@app_commands.describe(user="User to timeout", minutes="Minutes to timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_slash(interaction: discord.Interaction, user: discord.Member, minutes: int):
    try:
        await user.timeout(timedelta(minutes=minutes))
    except discord.Forbidden:
        await interaction.response.send_message("? I don't have permission to timeout that member.", ephemeral=True)
        return

    embed = build_embed(
        "User Timed Out",
        f"**User:** {user.mention}\n"
        f"**Duration:** {minutes} minutes",
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed)
    await log_mod_action(interaction.guild, embed)

@tree.command(name="modlog_set", description="Set the modlog channel")
@app_commands.describe(channel="Channel to set as modlog")
@commands.has_permissions(administrator=True)
async def modlog_set(interaction: discord.Interaction, channel: discord.TextChannel):
    modlog_channels[str(interaction.guild.id)] = channel.id
    save_modlogs()
    await interaction.response.send_message(f"? Modlog channel set to {channel.mention}")

@tree.command(name="modlog_get", description="Get the modlog channel")
@commands.has_permissions(administrator=True)
async def modlog_get(interaction: discord.Interaction):
    channel_id = modlog_channels.get(str(interaction.guild.id))
    if not channel_id:
        await interaction.response.send_message("?? No modlog channel set.")
        return
    channel = interaction.guild.get_channel(channel_id)
    if channel:
        await interaction.response.send_message(f"?? Modlog channel is {channel.mention}")
    else:
        await interaction.response.send_message("?? The modlog channel set no longer exists.")

# ---------- INTRODUCTION ON MENTION WITH COOLDOWN ----------

INTRO_MESSAGE = (
    "Hello! I'm Crimson, your moderation bot.\n"
    "I can help with moderation tasks like warn, kick, ban, and timeout.\n"
    "Use `?warn`, `?kick`, `?ban`, `?timeout` or their slash command equivalents.\n"
    "Admins can set a modlog channel using `/modlog_set`.\n"
    "Feel free to ask for help or check out the commands!"
)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions and len(message.mentions) == 1:
        user_id = str(message.author.id)
        now = datetime.utcnow()
        last_intro_time = mention_intro_cooldowns.get(user_id)

        if last_intro_time is None or (now - last_intro_time).total_seconds() > INTRO_COOLDOWN_HOURS * 3600:
            mention_intro_cooldowns[user_id] = now
            try:
                await message.channel.send(INTRO_MESSAGE)
            except:
                pass

    await bot.process_commands(message)

# ---------- ERROR HANDLING ----------

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("? You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("?? Missing required argument.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"?? Error: {error}")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("? You don't have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"?? Error: {error}", ephemeral=True)

bot.run(TOKEN)
