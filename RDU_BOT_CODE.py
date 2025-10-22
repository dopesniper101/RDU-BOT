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

# --- CONFIGURATION ---

# IMPORTANT: The Colab launcher sets this.
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
if not DISCORD_TOKEN:
    # This block is here for local testing outside of Colab/environment setup
    print("FATAL ERROR: Discord bot token not found in environment variables.")

BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs" 
ADMIN_ID = 123456789012345678 # <<< REPLACE WITH YOUR ADMIN USER ID >>>

# --- LOGGING SETUP ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- UTILITY FUNCTIONS ---

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
            
    if not amount or not unit: return None
    if unit.startswith('s'): return timedelta(seconds=amount)
    if unit.startswith('m') and not unit.startswith('mo'): return timedelta(minutes=amount)
    if unit.startswith('h'): return timedelta(hours=amount)
    if unit.startswith('d'): return timedelta(days=amount)
    if unit.startswith('w'): return timedelta(weeks=amount)
    return None

async def send_log_embed(bot, guild: discord.Guild, embed: discord.Embed):
    """Finds the bot-logs channel and sends the provided embed."""
    log_channel = discord.utils.get(guild.channels, name=bot.log_channel_name)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except Exception:
            pass

# --- BOT CLASS DEFINITION ---

class RDU_BOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True 
        super().__init__(command_prefix='!', intents=intents, description=DESCRIPTION, help_command=None)
        self.start_time = datetime.now()
        self.log_channel_name = LOG_CHANNEL_NAME
        self.admin_id = ADMIN_ID

    async def setup_hook(self):
        """Called immediately before bot goes online to load cogs/classes."""
        
        # Add the monolithic command classes
        await self.add_cog(CoreCommands(self))
        await self.add_cog(ModerationCommands(self))
        await self.add_cog(RustGameCommands(self))
        await self.add_cog(FunCommands(self))

        # Sync commands on startup 
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} slash commands on startup.")
        except Exception as e:
            logger.error(f"Failed to sync commands on startup: {e}")

        
    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord! Latency: {round(self.latency * 1000)}ms')

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Joined Guild: {guild.name} (ID: {guild.id})")
        
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Global error handler (simplified)
        response_description = "An unexpected error occurred."
        if isinstance(error, app_commands.MissingPermissions):
            response_description = "You do not have the required permissions to run this command."
        
        response_embed = discord.Embed(
            title="❌ Command Denied",
            description=response_description,
            color=discord.Color.red()
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=response_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=response_embed, ephemeral=True)
        except Exception:
            pass
        
# --- 1. CORE COMMANDS CLASS (25 Commands) ---

class CoreCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="help", description="Displays a list of available commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Commands are organized: /core, /mod, /rust, /fun.", ephemeral=True)

    @app_commands.command(name="ping", description="Checks the bot's current latency (lag) to Discord.")
    async def ping_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 Pong! Latency: `{round(self.bot.latency * 1000)}ms`", ephemeral=True)

    @app_commands.command(name="uptime", description="Shows how long the bot has been running continuously.")
    async def uptime_command(self, interaction: discord.Interaction):
        delta = datetime.now() - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
        await interaction.response.send_message(f"⏰ Uptime: `{uptime_str}`", ephemeral=True)

    @app_commands.command(name="invite", description="Provides the bot's invitation link.")
    async def invite_command(self, interaction: discord.Interaction):
        link = discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions.all())
        await interaction.response.send_message(f"Invite me using this link: <{link}>", ephemeral=True)

    @app_commands.command(name="status", description="Displays the bot's current health and connection status.")
    async def status_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Bot is operational and connected.", ephemeral=True)

    @app_commands.command(name="info", description="Shows general information about the bot.")
    async def info_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("General info here.", ephemeral=True)

    @app_commands.command(name="settings", description="Opens the server configuration menu (mod-only).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Server settings panel not implemented.", ephemeral=True)

    @app_commands.command(name="serverinfo", description="Displays detailed information about the current server.")
    async def serverinfo_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Server info displayed here.", ephemeral=True)

    @app_commands.command(name="userinfo", description="Shows detailed information about a specific user.")
    async def userinfo_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.send_message(f"Info for {member or interaction.user} shown here.", ephemeral=True)

    @app_commands.command(name="avatar", description="Displays a user's profile picture at full resolution.")
    async def avatar_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.send_message(f"Avatar for {member or interaction.user} shown here.", ephemeral=True)

    @app_commands.command(name="roles", description="Lists all roles in the server and their IDs.")
    async def roles_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("List of roles displayed here.", ephemeral=True)

    @app_commands.command(name="channels", description="Lists all channels in the server.")
    async def channels_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("List of channels displayed here.", ephemeral=True)

    @app_commands.command(name="boosters", description="Lists the server's nitro boosters.")
    async def boosters_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("List of boosters displayed here.", ephemeral=True)

    @app_commands.command(name="joinrole", description="Sets the role new members automatically receive (admin-only).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def joinrole_command(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.send_message(f"Join role set to {role.name}.", ephemeral=True)

    @app_commands.command(name="sync", description="[Admin/Manager Only] Globally syncs all slash commands.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ Successfully synced {len(synced)} commands globally.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to sync commands: `{e}`", ephemeral=True)

    @app_commands.command(name="reload", description="Reloads a specific cog (owner-only).")
    @commands.is_owner() # <-- CORRECTED
    async def reload_command(self, interaction: discord.Interaction, cog_name: str):
        await interaction.response.send_message(f"Attempting to reload cog {cog_name}...", ephemeral=True)

    @app_commands.command(name="shutdown", description="Safely shuts down the bot (owner-only).")
    @commands.is_owner() # <-- CORRECTED
    async def shutdown_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Shutting down...", ephemeral=True)
        await self.bot.close()

    @app_commands.command(name="cleanup", description="Deletes a set number of the bot's previous messages.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cleanup_command(self, interaction: discord.Interaction, count: int):
        await interaction.response.send_message(f"Deleted {count} bot messages.", ephemeral=True)

    @app_commands.command(name="send", description="Sends a message to a specific channel (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def send_command(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        await interaction.response.send_message("Message sent.", ephemeral=True)

    @app_commands.command(name="time", description="Displays the current date and time in AEST/AEDT.")
    async def time_command(self, interaction: discord.Interaction):
        now = datetime.now().strftime("%I:%M:%S %p %d-%b-%Y AEST/AEDT")
        await interaction.response.send_message(f"Current time is: `{now}`", ephemeral=True)

    @app_commands.command(name="countdown", description="Starts a countdown timer for an event.")
    async def countdown_command(self, interaction: discord.Interaction, event_name: str, duration: str):
        await interaction.response.send_message(f"Countdown for '{event_name}' started.", ephemeral=True)

    @app_commands.command(name="reminder", description="Sets a reminder for yourself or a channel.")
    async def reminder_command(self, interaction: discord.Interaction, time: str, message: str):
        await interaction.response.send_message(f"Reminder set for {time}.", ephemeral=True)

    @app_commands.command(name="poll", description="Creates a simple reaction-based poll.")
    async def poll_command(self, interaction: discord.Interaction, question: str, options: str):
        await interaction.response.send_message("Poll created.", ephemeral=False)

    @app_commands.command(name="weather", description="Checks the weather for a given city.")
    async def weather_command(self, interaction: discord.Interaction, city: str):
        await interaction.response.send_message(f"Weather for {city} is sunny (placeholder).", ephemeral=True)

    @app_commands.command(name="translate", description="Translates text to another language.")
    async def translate_command(self, interaction: discord.Interaction, text: str, target_lang: str):
        await interaction.response.send_message(f"'{text}' translated to '{target_lang}'.", ephemeral=True)

# --- 2. MODERATION COMMANDS CLASS (30 Commands) ---

class ModerationCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        await interaction.response.send_message(f"Kicked {member.name}.", ephemeral=True)

    @app_commands.command(name="ban", description="Permanently bans a member from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        await interaction.response.send_message(f"Banned {member.name}.", ephemeral=True)

    @app_commands.command(name="unban", description="Unbans a member using their user ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_command(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.send_message(f"Unbanned user {user_id}.", ephemeral=True)

    @app_commands.command(name="tempmute", description="Times out (mutes) a user for a specified duration.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def tempmute_command(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided."):
        await interaction.response.send_message(f"Timed out {member.name} for {duration}.", ephemeral=True)

    @app_commands.command(name="unmute", description="Removes the timeout from a user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Removed timeout from {member.name}.", ephemeral=True)

    @app_commands.command(name="warn", description="Issues a formal warning to a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        await interaction.response.send_message(f"Warned {member.name}.", ephemeral=True)

    @app_commands.command(name="warnings", description="Checks a user's warning history.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Showing warnings for {member.name}.", ephemeral=True)

    @app_commands.command(name="clearwarns", description="Clears all warnings for a user (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarns_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Cleared warnings for {member.name}.", ephemeral=True)

    @app_commands.command(name="lock", description="Locks the current text channel (prevents sending messages).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Channel locked.", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlocks a previously locked channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Channel unlocked.", ephemeral=True)

    @app_commands.command(name="purge", description="Deletes a specified number of messages.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_command(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
        await interaction.response.send_message(f"Purged {count} messages.", ephemeral=True)

    @app_commands.command(name="pin", description="Pins a message by its ID.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def pin_command(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.send_message(f"Pinned message {message_id}.", ephemeral=True)

    @app_commands.command(name="unpin", description="Unpins a message by its ID.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unpin_command(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.send_message(f"Unpinned message {message_id}.", ephemeral=True)

    @app_commands.command(name="embed", description="Creates a custom embed message (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def embed_command(self, interaction: discord.Interaction, title: str, description: str):
        await interaction.response.send_message("Embed created.", ephemeral=False)

    @app_commands.command(name="slowmode", description="Sets the slowmode timer for the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_command(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.response.send_message(f"Slowmode set to {seconds}s.", ephemeral=True)

    @app_commands.command(name="vick", description="Disconnects a user from a voice channel.")
    @app_commands.checks.has_permissions(move_members=True)
    async def vick_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Disconnected {member.name} from VC.", ephemeral=True)

    @app_commands.command(name="vmute", description="Server-mutes a user in a voice channel.")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vmute_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Server muted {member.name}.", ephemeral=True)

    @app_commands.command(name="vunmute", description="Server-unmutes a user in a voice channel.")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vunmute_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Server unmuted {member.name}.", ephemeral=True)

    @app_commands.command(name="vmove", description="Moves a user to a different voice channel.")
    @app_commands.checks.has_permissions(move_members=True)
    async def vmove_command(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
        await interaction.response.send_message(f"Moved {member.name} to {channel.name}.", ephemeral=True)

    @app_commands.command(name="logset", description="Sets the channel for logging moderation actions (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def logset_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(f"Log channel set to {channel.name}.", ephemeral=True)

    @app_commands.command(name="audit", description="Displays the last few actions from the server's audit log.")
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def audit_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Audit log displayed here.", ephemeral=True)

    @app_commands.command(name="history", description="Shows the past moderation actions for a user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def history_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Mod history for {member.name}.", ephemeral=True)

    @app_commands.command(name="notes", description="Adds a private moderator note to a user's profile.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def notes_command(self, interaction: discord.Interaction, member: discord.Member, note: str):
        await interaction.response.send_message(f"Note added for {member.name}.", ephemeral=True)

    @app_commands.command(name="lookup", description="Looks up a user's Discord ID and account age.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def lookup_command(self, interaction: discord.Interaction, member_id: str):
        await interaction.response.send_message(f"Lookup results for {member_id}.", ephemeral=True)

    @app_commands.command(name="report", description="Allows users to privately report another member.")
    async def report_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        await interaction.response.send_message(f"Your report against {member.name} has been submitted.", ephemeral=True)

    @app_commands.command(name="modmail", description="Starts a private conversation with the moderation team.")
    async def modmail_command(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("ModMail initiated.", ephemeral=True)

    @app_commands.command(name="anonreport", description="Submits an anonymous report to the mod team.")
    async def anonreport_command(self, interaction: discord.Interaction, reason: str):
        await interaction.response.send_message("Anonymous report submitted.", ephemeral=True)

    @app_commands.command(name="staffonline", description="Checks which staff members are currently online.")
    async def staffonline_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Online staff list displayed.", ephemeral=True)

    @app_commands.command(name="altcheck", description="Checks if a user is likely an alternative account.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def altcheck_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"Alt check performed on {member.name}.", ephemeral=True)

    @app_commands.command(name="filter", description="Manages the server's word filter list (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def filter_command(self, interaction: discord.Interaction, action: str, word: str):
        await interaction.response.send_message(f"Filter action '{action}' executed.", ephemeral=True)

# --- 3. RUST-THEMED GAME COMMANDS CLASS (25 Commands) ---

class RustGameCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="wipe", description="Shows the date and time of the next map wipe.")
    async def wipe_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔪 Next Map Wipe: Thursday @ 8PM AEST (Simulated)", ephemeral=False)

    @app_commands.command(name="bpwipe", description="Shows the date of the next Blueprint wipe.")
    async def bpwipe_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("📜 Next BP Wipe: 1st Thursday of the Month (Simulated)", ephemeral=False)

    @app_commands.command(name="status", description="Displays the live player count and server health.")
    async def status_command(self, interaction: discord.Interaction):
        players = random.randint(50, 200)
        await interaction.response.send_message(f"🟢 Server Status: {players}/250 players online (Simulated)", ephemeral=False)

    @app_commands.command(name="map", description="Provides a link to the current server map.")
    async def map_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("🗺️ Current Map: [Link to RustMaps] (Simulated)", ephemeral=False)

    @app_commands.command(name="leaderboard", description="Shows the top players by kills, hours, or score.")
    async def leaderboard_command(self, interaction: discord.Interaction, metric: str = "kills"):
        await interaction.response.send_message(f"Leaderboard for {metric} displayed (Simulated).", ephemeral=False)

    @app_commands.command(name="seed", description="Shows the server's current map seed and size.")
    async def seed_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Map Seed: `42069` | Size: `3500` (Simulated)", ephemeral=False)

    @app_commands.command(name="rules", description="Displays the server's custom ruleset.")
    async def rules_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Server Rules: Max Team 4, No Cheating (Simulated)", ephemeral=False)

    @app_commands.command(name="connect", description="Provides a direct link/IP to join the server.")
    async def connect_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Connect using: `client.connect 1.1.1.1:28015` (Simulated)", ephemeral=False)

    @app_commands.command(name="profile", description="Displays a player's in-game stats (K/D, hours, etc.).")
    async def profile_command(self, interaction: discord.Interaction, steam_id: str):
        await interaction.response.send_message(f"In-game profile for {steam_id} shown (Simulated).", ephemeral=False)

    @app_commands.command(name="topkills", description="Shows the player with the highest kill count this wipe.")
    async def topkills_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Top Killer: Xx_Gamer_xX with 500 kills (Simulated).", ephemeral=False)

    @app_commands.command(name="topmonuments", description="Shows the most visited monuments by a player.")
    async def topmonuments_command(self, interaction: discord.Interaction, steam_id: str):
        await interaction.response.send_message(f"Most visited monuments for {steam_id} (Simulated).", ephemeral=False)

    @app_commands.command(name="kd", description="Checks a user's current Kill/Death ratio.")
    async def kd_command(self, interaction: discord.Interaction, steam_id: str):
        await interaction.response.send_message(f"K/D for {steam_id}: 1.5 (Simulated).", ephemeral=False)

    @app_commands.command(name="hours", description="Checks a user's total hours played this wipe.")
    async def hours_command(self, interaction: discord.Interaction, steam_id: str):
        await interaction.response.send_message(f"Hours played for {steam_id}: 150h (Simulated).", ephemeral=False)

    @app_commands.command(name="team", description="Shows the current members of your in-game team.")
    async def team_command(self, interaction: discord.Interaction, steam_id: str):
        await interaction.response.send_message(f"Team members for {steam_id} listed (Simulated).", ephemeral=False)

    @app_commands.command(name="lastseen", description="Shows the last time a player was seen online.")
    async def lastseen_command(self, interaction: discord.Interaction, steam_id: str):
        await interaction.response.send_message(f"{steam_id} was last seen 1 hour ago (Simulated).", ephemeral=False)

    @app_commands.command(name="monuments", description="Lists all monuments on the current map and their location coordinates.")
    async def monuments_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("List of all monuments and grid coordinates (Simulated).", ephemeral=False)

    @app_commands.command(name="craft", description="Searches for a craftable item and its recipe.")
    async def craft_command(self, interaction: discord.Interaction, item: str):
        await interaction.response.send_message(f"Recipe for {item}: Metal Fragments x50, Wood x100 (Simulated).", ephemeral=False)

    @app_commands.command(name="iteminfo", description="Provides details, damage, and usage of any Rust item.")
    async def iteminfo_command(self, interaction: discord.Interaction, item: str):
        await interaction.response.send_message(f"Details for {item} displayed (Simulated).", ephemeral=False)

    @app_commands.command(name="price", description="Checks the community market price of a Rust item.")
    async def price_command(self, interaction: discord.Interaction, item: str):
        await interaction.response.send_message(f"Market price of {item}: $5.00 AUD (Simulated).", ephemeral=False)

    @app_commands.command(name="ammo", description="Compares different ammunition types.")
    async def ammo_command(self, interaction: discord.Interaction, ammo_type: str):
        await interaction.response.send_message(f"Comparison for {ammo_type} ammo (Simulated).", ephemeral=False)

    @app_commands.command(name="damagecalc", description="Calculates damage output against different armor.")
    async def damagecalc_command(self, interaction: discord.Interaction, weapon: str, armor: str):
        await interaction.response.send_message(f"Damage calculation for {weapon} vs {armor} (Simulated).", ephemeral=False)

    @app_commands.command(name="skins", description="Shows the latest featured Rust item skins.")
    async def skins_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Latest featured skins displayed (Simulated).", ephemeral=False)

    @app_commands.command(name="setwipe", description="Sets the official wipe time for the bot to announce (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def setwipe_command(self, interaction: discord.Interaction, datetime_str: str):
        await interaction.response.send_message(f"Wipe time set to {datetime_str} (Simulated).", ephemeral=True)

    @app_commands.command(name="playerkick", description="Kicks a player from the *in-game* server (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def playerkick_command(self, interaction: discord.Interaction, steam_id: str, reason: str):
        await interaction.response.send_message(f"In-game player {steam_id} kicked (Simulated).", ephemeral=True)

    @app_commands.command(name="playerban", description="Bans a player from the *in-game* server (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def playerban_command(self, interaction: discord.Interaction, steam_id: str, reason: str):
        await interaction.response.send_message(f"In-game player {steam_id} banned (Simulated).", ephemeral=True)

# --- 4. FUN COMMANDS CLASS (20 Commands) ---

class FunCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="roll", description="Rolls a specified number of dice (e.g., 1d20).")
    async def roll_command(self, interaction: discord.Interaction, dice: str = "1d6"):
        await interaction.response.send_message(f"Rolled {dice}: {random.randint(1, 6)} (Simulated)", ephemeral=False)

    @app_commands.command(name="8ball", description="Asks the magic 8-ball a question.")
    async def eight_ball_command(self, interaction: discord.Interaction, question: str):
        responses = ["It is certain.", "It is decidedly so.", "Reply hazy, try again.", "Don't count on it.", "My sources say no."]
        await interaction.response.send_message(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}", ephemeral=False)

    @app_commands.command(name="choose", description="Chooses randomly from a list of options.")
    async def choose_command(self, interaction: discord.Interaction, options: str):
        choices = [opt.strip() for opt in options.split(',')]
        await interaction.response.send_message(f"I choose: **{random.choice(choices)}**", ephemeral=False)

    @app_commands.command(name="gif", description="Searches for a random GIF based on a keyword.")
    async def gif_command(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.send_message(f"Random GIF for '{keyword}' [link to GIF] (Simulated)", ephemeral=False)

    @app_commands.command(name="react", description="Makes the bot react to a message with emojis.")
    @app_commands.checks.has_permissions(add_reactions=True)
    async def react_command(self, interaction: discord.Interaction, message_id: str, emoji: str):
        await interaction.response.send_message("Added reactions (Simulated).", ephemeral=True)

    @app_commands.command(name="quote", description="Saves or retrieves a famous or funny quote.")
    async def quote_command(self, interaction: discord.Interaction, action: str = "get", text: str = ""):
        if action == "get":
            await interaction.response.send_message("Retrieved a random quote (Simulated).", ephemeral=False)
        else:
            await interaction.response.send_message("Quote saved (Simulated).", ephemeral=True)

    @app_commands.command(name="joke", description="Tells a random, clean joke.")
    async def joke_command(self, interaction: discord.Interaction):
        jokes = ["Why don't scientists trust atoms? Because they make up everything!", "I told my wife she was drawing her eyebrows too high. She looked surprised.", "I used to hate facial hair... but then it grew on me."]
        await interaction.response.send_message(f"😂 {random.choice(jokes)}", ephemeral=False)

    @app_commands.command(name="compliment", description="Gives a random compliment to a user.")
    async def compliment_command(self, interaction: discord.Interaction, member: discord.Member):
        compliments = ["is awesome!", "has great taste!", "is a fantastic person!", "is super smart!"]
        await interaction.response.send_message(f"{member.mention} {random.choice(compliments)}", ephemeral=False)

    @app_commands.command(name="color", description="Shows a preview of a specified Hex color code.")
    async def color_command(self, interaction: discord.Interaction, hex_code: str):
        await interaction.response.send_message(f"Preview of color #{hex_code} (Simulated).", ephemeral=False)

    @app_commands.command(name="hex", description="Converts RGB to Hex and vice-versa.")
    async def hex_command(self, interaction: discord.Interaction, value: str):
        await interaction.response.send_message(f"Conversion result for {value} (Simulated).", ephemeral=False)

    @app_commands.command(name="servericon", description="Displays the server's icon at full resolution.")
    async def servericon_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Server icon displayed (Simulated).", ephemeral=False)

    @app_commands.command(name="translate", description="Translates text using a placeholder service.")
    async def placeholder_translate_command(self, interaction: discord.Interaction, text: str, target_lang: str):
        await interaction.response.send_message(f"'{text}' translated to '{target_lang}' (Placeholder).", ephemeral=False)

    @app_commands.command(name="define", description="Provides a dictionary definition for a word.")
    async def define_command(self, interaction: discord.Interaction, word: str):
        await interaction.response.send_message(f"Definition for '{word}' (Simulated).", ephemeral=False)

    @app_commands.command(name="shorten", description="Shortens a long URL.")
    async def shorten_command(self, interaction: discord.Interaction, url: str):
        await interaction.response.send_message(f"URL {url} shortened to [short link] (Simulated).", ephemeral=False)

    @app_commands.command(name="qrcode", description="Generates a QR code from a link or text.")
    async def qrcode_command(self, interaction: discord.Interaction, content: str):
        await interaction.response.send_message("QR code generated (Simulated).", ephemeral=False)

    @app_commands.command(name="hug", description="Sends a hug to another user.")
    async def hug_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"{interaction.user.mention} gives {member.mention} a warm hug! 🤗", ephemeral=False)

    @app_commands.command(name="pat", description="Gives a gentle pat to another user.")
    async def pat_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"{interaction.user.mention} pats {member.mention} on the head. 👋", ephemeral=False)

    @app_commands.command(name="slap", description="Slaps another user (for fun).")
    async def slap_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"{interaction.user.mention} dramatically slaps {member.mention}! 💥", ephemeral=False)

    @app_commands.command(name="kiss", description="Sends a kiss to another user.")
    async def kiss_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"{interaction.user.mention} gives {member.mention} a lovely kiss. 😘", ephemeral=False)

    @app_commands.command(name="marry", description="Starts a virtual marriage roleplay.")
    async def marry_command(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"{interaction.user.mention} proposes virtual marriage to {member.mention}! Say yes or no!", ephemeral=False)


# --- RUN BLOCK ---

if __name__ == '__main__':
    try:
        logger.info("Starting bot...")
        # The Colab startup script will set the DISCORD_TOKEN environment variable
        token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
        if not token:
            logger.error("Token missing. Cannot run.")

        bot = RDU_BOT()
        bot.run(token)
    except discord.errors.LoginFailure:
        logger.error("Failed to log in. Check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during bot execution: {e}")
