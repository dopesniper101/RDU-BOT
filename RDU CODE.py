import os
import sys
import logging
from datetime import datetime, timedelta
import asyncio
import random
from typing import Optional

# Imports will now succeed because the Colab launcher guaranteed the installation
import discord
from discord.ext import commands
from discord import app_commands, utils, VoiceClient
import discord.sinks as sinks


# --- CONFIGURATION ---

# IMPORTANT: The Colab launcher relies on this check. 
# Ensure your token is set in the Colab 'Secrets' tab as DISCORD_BOT_TOKEN
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
if not DISCORD_TOKEN:
    print("FATAL ERROR: Discord bot token not found in environment variables.")
    sys.exit(1)

BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs" 
ADMIN_ID = 123456789012345678 # Placeholder for your Admin User ID 

# --- LOGGING SETUP ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- BOT SETUP AND INTENTS ---

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True 

bot = commands.Bot(command_prefix='!', intents=intents, description=DESCRIPTION, help_command=None)
bot.start_time = datetime.now()
voice_clients = {}

# --- UTILITY FUNCTIONS ---

async def send_log_embed(guild: discord.Guild, embed: discord.Embed):
    """Finds the bot-logs channel and sends the provided embed."""
    log_channel = discord.utils.get(guild.channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except Exception:
            pass

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parses a duration string (e.g., '1h', '30m', '5d') into a timedelta object."""
    duration_str = duration_str.lower()
    amount = 0
    unit = ''
    
    for char in duration_str:
        if char.isdigit():
            amount = amount * 10 + int(char)
        elif char.isalpha():
            unit += char
            
    if not amount or not unit:
        return None

    if unit.startswith('s'):
        return timedelta(seconds=amount)
    elif unit.startswith('m') and not unit.startswith('mo'):
        return timedelta(minutes=amount)
    elif unit.startswith('h'):
        return timedelta(hours=amount)
    elif unit.startswith('d'):
        return timedelta(days=amount)
    elif unit.startswith('w'):
        return timedelta(weeks=amount)
    else:
        return None

# --- VOICE RECORDING CALLBACK ---

async def finished_recording_callback(sink: sinks.WaveSink, text_channel: discord.TextChannel, *args):
    """
    Called when a voice recording is stopped. Sends the recorded audio files.
    This provides the multi-track (Craig-style) output.
    """
    vc: VoiceClient = sink.vc
    guild = vc.guild
    
    # 1. Disconnect and clean up
    await vc.disconnect()
    if guild.id in voice_clients:
        del voice_clients[guild.id]
        
    # 2. Prepare files for sending (one file per speaker/user)
    files = []
    recorded_users = []
    
    for user_id, audio in sink.audio_data.items():
        user = bot.get_user(user_id)
        display_name = user.display_name if user else f"unknown_user_{user_id}"
        file_name = f"{display_name.replace(' ', '_')}_{user_id}.{sink.encoding}"
        files.append(discord.File(audio.file, filename=file_name))
        recorded_users.append(user.mention if user else f"User ID `{user_id}`")

    # 3. Send confirmation and the files
    user_list = ", ".join(recorded_users)
    embed = discord.Embed(
        title="🎙️ Recording Finished!",
        description=f"**Recorded Speakers:** {user_list}\n*You should receive one file per speaker for multi-track editing.*",
        color=discord.Color.dark_teal()
    )
    await text_channel.send(embed=embed, files=files)
    
    # 4. Log the event
    log_embed = discord.Embed(
        title="🔊 Voice Recording Completed", 
        description=f"Recording finished in voice channel: `{vc.channel.name}`.\nSpeakers: {len(recorded_users)}", 
        color=discord.Color.dark_teal()
    )
    await send_log_embed(guild, log_embed)


# --- EVENTS ---

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    logger.info(f"Joined Guild: {guild.name} (ID: {guild.id})")

    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        channel = guild.system_channel
    else:
        channel = utils.get(guild.text_channels, position=0)
        if not channel or not channel.permissions_for(guild.me).send_messages:
            return

    embed = discord.Embed(
        title=f"Thanks for inviting {BOT_NAME}!",
        description="I'm here to help manage your RUST DOWN UNDER server. I've synced my slash commands!\n\n**Start here:**\n- Use `/help` to see available commands.\n- I will try to create a text channel named `#bot-logs` for moderation actions.",
        color=discord.Color.dark_green()
    )
    await channel.send(embed=embed)
    
    if not utils.get(guild.channels, name=LOG_CHANNEL_NAME):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        try:
            await guild.create_text_channel(LOG_CHANNEL_NAME, overwrites=overwrites, reason="Bot log channel setup.")
        except discord.Forbidden:
            pass 


# --- CORE COMMANDS ---

@bot.tree.command(name="help", description="Shows the most important commands you can use. (Ephemeral/30s)")
async def help_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in servers!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    CORE_COMMANDS = {
        "ping", "userinfo", "serverinfo", "uptime", "wipe", "status", "map", 
        "rules", "kick", "tempmute", "join", "stop", "leave", "sync" 
    }

    allowed_commands = []
    for command in bot.tree.walk_commands():
        if command.name not in CORE_COMMANDS:
            continue
            
        is_allowed = True
        if hasattr(command, '_checks') and command._checks:
            for check in command._checks:
                try:
                    await discord.utils.maybe_coroutine(check, interaction)
                except (app_commands.MissingPermissions, app_commands.CheckFailure):
                    is_allowed = False
                    break
        
        if is_allowed:
            allowed_commands.append(f"`/{command.name}` - {command.description}")

    if allowed_commands:
        commands_list = "\n".join(sorted(allowed_commands))
        embed = discord.Embed(
            title="Aussie RDU Bot Essential Commands 🇦🇺",
            description=f"**The most essential commands you can use:**\n\n{commands_list}",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Only essential commands are shown. This message is only visible to you.")
    else:
        embed = discord.Embed(
            title="No Commands Available",
            description="You do not currently have permission to use any essential commands.",
            color=discord.Color.red()
        )
        embed.set_footer(text="This message is only visible to you.")

    await interaction.followup.send(embed=embed, ephemeral=True)
    
    log_embed = discord.Embed(description=f"Help command used by {interaction.user.mention}.", color=discord.Color.light_grey())
    await send_log_embed(interaction.guild, log_embed)


# --- VOICE RECORDING COMMANDS (CRAIG-STYLE) ---

@bot.tree.command(name="join", description="Joins your voice channel and starts multi-track recording (Craig-style).")
@app_commands.checks.has_permissions(move_members=True)
async def join_command(interaction: discord.Interaction):
    if not interaction.guild or not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ You must be in a voice channel to use this command!", ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel
    guild_id = interaction.guild_id

    if guild_id in voice_clients and voice_clients[guild_id].is_connected():
        await interaction.response.send_message(f"❌ I'm already recording in {voice_clients[guild_id].channel.mention}!", ephemeral=True)
        return

    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if guild_id in voice_clients:
            vc = await voice_clients[guild_id].move_to(voice_channel)
        else:
            vc = await voice_channel.connect()
            voice_clients[guild_id] = vc
    except discord.Forbidden:
        await interaction.followup.send("❌ I do not have permission to join that voice channel.", ephemeral=True)
        return
    except Exception as e:
        logger.error(f"Voice connect error: {e}")
        await interaction.followup.send("❌ An error occurred while trying to connect to the voice channel. Check bot permissions.", ephemeral=True)
        return

    vc.start_recording(
        sinks.WaveSink(), 
        finished_recording_callback, 
        interaction.channel 
    )

    embed = discord.Embed(
        title="🔴 Recording Started (Multi-Track)",
        description=f"I have joined and started recording **{voice_channel.mention}**.\nType `/stop` to end the recording and receive the files.",
        color=discord.Color.red()
    )
    await interaction.followup.send(embed=embed)
    
    log_embed = discord.Embed(
        title="🎤 Voice Recording Started", 
        description=f"**Channel:** {voice_channel.mention}\n**Started By:** {interaction.user.mention}", 
        color=discord.Color.red()
    )
    await send_log_embed(interaction.guild, log_embed)


@bot.tree.command(name="stop", description="Stops the current recording and sends the audio file(s).")
@app_commands.checks.has_permissions(move_members=True)
async def stop_command(interaction: discord.Interaction):
    guild_id = interaction.guild_id

    if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
        await interaction.response.send_message("❌ I am not currently recording in any channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    vc: VoiceClient = voice_clients[guild_id]

    try:
        vc.stop_recording() 
        await interaction.followup.send("✅ Stopping recording and processing audio files. They will be sent to the initial text channel shortly.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        await interaction.followup.send("❌ An error occurred while trying to stop the recording.", ephemeral=True)
        if guild_id in voice_clients:
            await voice_clients[guild_id].disconnect()
            del voice_clients[guild_id]


@bot.tree.command(name="leave", description="Stops the bot and disconnects it from the voice channel.")
async def leave_command(interaction: discord.Interaction):
    guild_id = interaction.guild_id

    if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
        await interaction.response.send_message("❌ I am not currently in a voice channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    vc: VoiceClient = voice_clients[guild_id]
    
    if vc.is_recording():
        vc.stop_recording()
    
    await vc.disconnect()
    del voice_clients[guild_id]

    await interaction.followup.send("👋 Disconnected from the voice channel.", ephemeral=True)
    
    log_embed = discord.Embed(
        title="🔌 Voice Disconnected", 
        description=f"**Actioned By:** {interaction.user.mention}", 
        color=discord.Color.blue()
    )
    await send_log_embed(interaction.guild, log_embed)

# --- MODERATION COMMANDS (10) ---

@bot.tree.command(name="kick", description="Kicks a user from the server.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_command(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    if member.top_role >= interaction.user.top_role and member != interaction.user:
        await interaction.followup.send("❌ You cannot kick this user because their role is equal to or higher than yours.", ephemeral=True)
        return
        
    try:
        await member.kick(reason=reason)
        await interaction.followup.send(f"✅ Kicked {member.mention} for reason: `{reason}`.", ephemeral=False)
        
        embed = discord.Embed(
            title="🚫 User Kicked", 
            description=f"**Target:** {member.mention} (`{member.id}`)\n**Moderator:** {interaction.user.mention}\n**Reason:** `{reason}`", 
            color=discord.Color.red()
        )
        await send_log_embed(interaction.guild, embed)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ I do not have permission to kick that user.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: `{e}`", ephemeral=True)

@bot.tree.command(name="tempmute", description="Mutes a user for a specified duration (e.g., 30m, 1h, 1d).")
@app_commands.describe(duration='Time (e.g., 30m, 1h, 1d). Max 28 days.')
@app_commands.checks.has_permissions(moderate_members=True)
async def tempmute_command(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided."):
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    td = parse_duration(duration)
    if td is None:
        await interaction.followup.send("❌ Invalid duration format. Use: `30m`, `1h`, `1d`, etc.", ephemeral=True)
        return

    if td > timedelta(weeks=4):
        await interaction.followup.send("❌ The maximum duration for a timeout is 28 days.", ephemeral=True)
        return

    try:
        await member.timeout(td, reason=reason)
        
        end_time = datetime.now() + td
        formatted_end = discord.utils.format_dt(end_time, style='R') 
        
        await interaction.followup.send(f"✅ Timed out {member.mention} for `{duration}`. End time: {formatted_end}.", ephemeral=False)

        embed = discord.Embed(
            title="🔇 User Timed Out", 
            description=f"**Target:** {member.mention} (`{member.id}`)\n**Moderator:** {interaction.user.mention}\n**Duration:** `{duration}`\n**Reason:** `{reason}`", 
            color=discord.Color.orange()
        )
        await send_log_embed(interaction.guild, embed)

    except discord.Forbidden:
        await interaction.followup.send("❌ I do not have permission to time out that user.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: `{e}`", ephemeral=True)


# --- UTILITY COMMANDS (5) ---

@bot.tree.command(name="ping", description="Shows the bot's latency.")
async def ping_command(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latency: `{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="uptime", description="Shows how long the bot has been running.")
async def uptime_command(interaction: discord.Interaction):
    delta = datetime.now() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    await interaction.response.send_message(f"⏰ Uptime: `{uptime_str}`", ephemeral=True)

@bot.tree.command(name="serverinfo", description="Displays information about the current server.")
async def serverinfo_command(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Info for {guild.name}", color=discord.Color.blue())
    
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Created On", value=discord.utils.format_dt(guild.created_at, style='D'), inline=True)
    embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="userinfo", description="Displays information about a user.")
async def userinfo_command(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    
    embed = discord.Embed(title=f"User Info for {member.display_name}", color=member.color if member.color != discord.Color.default() else discord.Color.greyple())
    
    embed.add_field(name="Username", value=f"@{member.name}", inline=True)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style='D'), inline=True)
    
    if isinstance(member, discord.Member):
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style='D'), inline=True)
        top_role = member.top_role if member.top_role else "None"
        embed.add_field(name="Top Role", value=top_role.mention, inline=True)
        embed.add_field(name="Roles Count", value=len(member.roles) - 1, inline=True)
        
    embed.add_field(name="User ID", value=f"`{member.id}`", inline=True)
    
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="sync", description="[Admin Only] Globally syncs all slash commands.")
async def sync_command(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ This command is for the bot owner only.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Successfully synced {len(synced)} commands globally.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to sync commands: `{e}`", ephemeral=True)


# --- RUST-THEMED COMMANDS (4) ---

@bot.tree.command(name="wipe", description="Announces the next expected server wipe time.")
async def wipe_command(interaction: discord.Interaction):
    today = datetime.now().weekday()
    days_until_thursday = (3 - today + 7) % 7
    
    if days_until_thursday == 0 and datetime.now().hour >= 20:
        days_until_thursday = 7
    elif days_until_thursday == 0:
        wipe_time = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
    
    if days_until_thursday > 0:
        wipe_time = (datetime.now() + timedelta(days=days_until_thursday)).replace(hour=20, minute=0, second=0, microsecond=0)
    
    wipe_timestamp = discord.utils.format_dt(wipe_time, style='R')
    
    embed = discord.Embed(
        title="🔪 Next Server Wipe",
        description=f"The next scheduled **Map Wipe** is: **{wipe_timestamp}** (8:00 PM AEST/AEDT).\n\n*Note: This is an estimated map wipe. Blueprint (BP) wipes happen on the first Thursday of the month.*",
        color=discord.Color.teal()
    )
    embed.set_footer(text="Get ready to lose your progress (again!).")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="status", description="Checks the current status of the Rust server.")
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    server_online = random.choice([True, True, True, False])
    if server_online:
        players = random.randint(50, 200)
        max_players = 250
        fps = random.randint(50, 150)
        last_wipe = (datetime.now() - timedelta(days=random.randint(1, 6))).strftime("%Y-%m-%d")
        status_color = discord.Color.green()
        status_text = "🟢 Online"
    else:
        players = 0
        max_players = 250
        fps = 0
        last_wipe = "N/A"
        status_color = discord.Color.red()
        status_text = "🔴 Offline"

    embed = discord.Embed(
        title="Rust Down Under Server Status",
        description=f"**Status:** {status_text}",
        color=status_color
    )
    embed.add_field(name="Players", value=f"{players}/{max_players}", inline=True)
    embed.add_field(name="Server FPS", value=f"`{fps}`", inline=True)
    embed.add_field(name="Last Wipe", value=last_wipe, inline=True)
    embed.set_footer(text="Data is simulated. For real-time data, check server list providers.")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="map", description="Shows a link to the current server map.")
async def map_command(interaction: discord.Interaction):
    map_link = "https://rustmaps.com/map/6478d3882736b400010c7104"
    embed = discord.Embed(
        title="🗺️ Current Server Map",
        description=f"Click [here]({map_link}) to view the current map on RustMaps.com.\n\nSeed: `42069` | Size: `3500`",
        color=discord.Color.dark_green()
    )
    embed.set_image(url="https://i.imgur.com/G5g2mJg.png")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rules", description="Displays the server rules.")
async def rules_command(interaction: discord.Interaction):
    rules_text = (
        "**1. No cheating or exploiting.**\n"
        "**2. No toxic or excessively abusive chat.**\n"
        "**3. Base design exploiting is prohibited.**\n"
        "**4. Stream sniping is forbidden.**\n"
        "**5. Max team size is 4 (no alliances).**"
    )
    embed = discord.Embed(
        title="📜 Server Rules & Guidelines",
        description=rules_text,
        color=discord.Color.purple()
    )
    embed.set_footer(text="Report rule breakers to a staff member with evidence.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- ERROR HANDLER ---

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log_title = "🚨 UNHANDLED COMMAND ERROR"
    log_color = discord.Color.dark_red()
    
    if isinstance(error, app_commands.MissingPermissions):
        response_description = "You do not have the required permissions to run this command."
        log_description = f"**Moderator:** {interaction.user.mention} (ID: `{interaction.user.id}`)\n**Command:** `/{interaction.command.name}`\n**Error:** Missing Permissions."
        response_color = discord.Color.red()
    elif isinstance(error, app_commands.CommandNotFound):
        response_description = "Command not found. Please try `/help`."
        log_description = f"**User:** {interaction.user.mention}\n**Error:** Command Not Found."
        response_color = discord.Color.yellow()
    else:
        logger.error(f"Unhandled command error in {interaction.command.name}: {error.__class__.__name__}: {error}")
        response_description = f"An unexpected error occurred while running `/{interaction.command.name}`. The developer has been notified."
        log_description = f"**User:** {interaction.user.mention} (ID: `{interaction.user.id}`)\n**Command:** `/{interaction.command.name}`\n**Error Type:** {error.__class__.__name__}\n**Detail:** `{error}`"
        response_color = discord.Color.red()
        
    response_embed = discord.Embed(
        title="❌ Command Denied",
        description=response_description,
        color=response_color
    )
    try:
        if interaction.response.is_done():
             await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
             await interaction.response.send_message(embed=response_embed, ephemeral=True)
    except Exception:
        pass

    if hasattr(interaction, 'guild') and interaction.guild is not None:
        log_embed = discord.Embed(title=log_title, description=log_description, color=log_color)
        await send_log_embed(interaction.guild, log_embed)

# --- RUN BLOCK ---

if __name__ == '__main__':
    try:
        logger.info("Starting bot...")
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.error("Failed to log in. Check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during bot execution: {e}")
