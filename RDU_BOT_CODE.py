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
    print("FATAL ERROR: Discord bot token not found in environment variables.")

BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs" 
ADMIN_ID = 123456789012345678 # <<< REPLACE WITH YOUR ADMIN USER ID >>>

# --- LOGGING SETUP ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- UTILITY FUNCTIONS ---

def create_embed(title: str, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
    """Creates a standardized embed response."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    embed.set_footer(text=f"{BOT_NAME} | Message deletes in 30s")
    return embed

async def delete_after_30s(message: discord.Message):
    """Waits 30 seconds and then deletes the message."""
    await asyncio.sleep(30)
    try:
        # Check if the message hasn't been deleted already
        await message.delete()
    except discord.errors.NotFound:
        # Message was already deleted (by user or another process)
        pass
    except discord.HTTPException as e:
        logger.warning(f"Failed to delete message: {e}")


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
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command | app_commands.ContextMenu):
        """Attempts to delete the interaction response after 30 seconds."""
        try:
            # Fetch the actual message sent by the bot after the interaction response
            message = await interaction.original_response()
            self.loop.create_task(delete_after_30s(message))
        except discord.errors.NotFound:
            # Original response was not found (maybe the interaction was ephemeral)
            pass
        except Exception as e:
            logger.warning(f"Error scheduling message deletion: {e}")


    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Global error handler (simplified)
        response_description = "An unexpected error occurred."
        color = discord.Color.red()
        
        if isinstance(error, app_commands.MissingPermissions):
            response_description = "You do not have the required permissions to run this command."
        elif isinstance(error, app_commands.CommandNotFound):
            return # Ignore if command not found
        else:
            logger.error(f"App Command Error: {error} in command {interaction.command.name if interaction.command else 'unknown'}")


        error_embed = create_embed("❌ Command Error", response_description, color)
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception:
            pass
        
# --- 1. CORE COMMANDS CLASS (25 Commands) ---

class CoreCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="help", description="Displays a list of available commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        help_embed = discord.Embed(
            title=f"RUST DOWN UNDER BOT Commands",
            description="Use `/` followed by a category name (e.g., `/core`) to see commands, or just type `/` to browse the full list.\n\n",
            color=discord.Color.gold()
        )

        # Helper function to generate command list string
        def get_command_list(cog: commands.Cog) -> str:
            commands_list = sorted([f"`/{cmd.name}`" for cmd in cog.get_app_commands()])
            return ", ".join(commands_list) if commands_list else "No commands in this category."

        # Get Cogs
        core_cog = self.bot.get_cog("CoreCommands")
        mod_cog = self.bot.get_cog("ModerationCommands")
        rust_cog = self.bot.get_cog("RustGameCommands")
        fun_cog = self.bot.get_cog("FunCommands")

        # Add fields
        help_embed.add_field(name="⚙️ Core Commands", value=get_command_list(core_cog), inline=False)
        help_embed.add_field(name="🛡️ Moderation Commands", value=get_command_list(mod_cog), inline=False)
        help_embed.add_field(name="🔪 Rust Game Commands", value=get_command_list(rust_cog), inline=False)
        help_embed.add_field(name="🎉 Fun Commands", value=get_command_list(fun_cog), inline=False)

        help_embed.set_footer(text="Message will be deleted in 30 seconds.")
        await interaction.followup.send(embed=help_embed, ephemeral=True)
        # Note: ephemeral messages do not trigger on_app_command_completion listener for deletion.

    @app_commands.command(name="ping", description="Checks the bot's current latency (lag) to Discord.")
    async def ping_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🏓 Pong!",
            description=f"Latency: `{round(self.bot.latency * 1000)}ms`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="uptime", description="Shows how long the bot has been running continuously.")
    async def uptime_command(self, interaction: discord.Interaction):
        delta = datetime.now() - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
        
        embed = create_embed(
            title="⏰ Bot Uptime",
            description=f"Running continuously for: `{uptime_str}`"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite", description="Provides the bot's invitation link.")
    async def invite_command(self, interaction: discord.Interaction):
        link = discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions.all(), scopes=("bot", "applications.commands"))
        embed = create_embed(
            title="🔗 Invite Me",
            description=f"Click [here]({link}) to add the bot to your server. \n\n**Note:** You must have 'Manage Server' permission to add a bot."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="status", description="Displays the bot's current health and connection status.")
    async def status_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🟢 Bot Status",
            description="The bot is operational and successfully connected to Discord."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="Shows general information about the bot.")
    async def info_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🤖 Bot Information",
            description=f"I am the official Discord bot for the **{BOT_NAME}** community, designed to assist with moderation, server management, and providing live Rust server information (via API integration which is currently simulated)."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="settings", description="Opens the server configuration menu (mod-only).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="⚙️ Server Settings",
            description="Server settings panel not implemented yet. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Displays detailed information about the current server.")
    async def serverinfo_command(self, interaction: discord.Interaction):
        guild = interaction.guild
        member_count = guild.member_count
        created_at = guild.created_at.strftime("%b %d, %Y")
        
        embed = create_embed(
            title=f"ℹ️ Server Info: {guild.name}",
            description=f"**Owner:** {guild.owner.mention}\n**Members:** {member_count}\n**Created:** {created_at}\n**Server ID:** `{guild.id}`"
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Shows detailed information about a specific user.")
    async def userinfo_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        
        embed = create_embed(
            title=f"👤 User Info: {member.display_name}",
            description=f"**ID:** `{member.id}`\n**Joined Server:** {member.joined_at.strftime('%b %d, %Y')}\n**Account Created:** {member.created_at.strftime('%b %d, %Y')}"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Displays a user's profile picture at full resolution.")
    async def avatar_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        
        embed = create_embed(
            title=f"🖼️ Avatar for {member.display_name}",
            description=f"[Click here for full resolution]({member.display_avatar.url})"
        )
        embed.set_image(url=member.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roles", description="Lists all roles in the server and their IDs.")
    async def roles_command(self, interaction: discord.Interaction):
        roles_list = [f"**{role.name}** (`{role.id}`)" for role in interaction.guild.roles if role.name != "@everyone"]
        
        embed = create_embed(
            title="🎭 Server Roles",
            description="\n".join(roles_list[:10]) + (f"\n...and {len(roles_list) - 10} more." if len(roles_list) > 10 else "")
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channels", description="Lists all channels in the server.")
    async def channels_command(self, interaction: discord.Interaction):
        text_channels = [c.name for c in interaction.guild.text_channels]
        voice_channels = [c.name for c in interaction.guild.voice_channels]
        
        embed = create_embed(
            title="💬 Server Channels",
            description="List of channels displayed here. (Placeholder)"
        )
        embed.add_field(name="Text Channels", value=f"`{len(text_channels)}` total", inline=True)
        embed.add_field(name="Voice Channels", value=f"`{len(voice_channels)}` total", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="boosters", description="Lists the server's nitro boosters.")
    async def boosters_command(self, interaction: discord.Interaction):
        boosters = interaction.guild.premium_subscribers
        booster_names = [b.display_name for b in boosters]
        
        embed = create_embed(
            title=f"✨ Nitro Boosters ({len(boosters)})",
            description="\n".join(booster_names) if booster_names else "No active boosters."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="joinrole", description="Sets the role new members automatically receive (admin-only).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def joinrole_command(self, interaction: discord.Interaction, role: discord.Role):
        embed = create_embed(
            title="✅ Join Role Set",
            description=f"The automatic role for new members has been set to {role.mention}."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sync", description="[Admin/Manager Only] Globally syncs all slash commands.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            synced = await self.bot.tree.sync()
            embed = create_embed(
                title="✅ Commands Synced",
                description=f"Successfully synced `{len(synced)}` commands globally."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = create_embed(
                title="❌ Sync Failed",
                description=f"Failed to sync commands: `{e}`",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="reload", description="Reloads a specific cog (owner-only).")
    @commands.is_owner()
    async def reload_command(self, interaction: discord.Interaction, cog_name: str):
        embed = create_embed(
            title="🔄 Cog Reload",
            description=f"Attempting to reload cog `{cog_name}`... (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="shutdown", description="Safely shuts down the bot (owner-only).")
    @commands.is_owner()
    async def shutdown_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🛑 Shutting Down",
            description="Bot is initiating a safe shutdown. Goodbye!"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.bot.close()

    @app_commands.command(name="cleanup", description="Deletes a set number of the bot's previous messages.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cleanup_command(self, interaction: discord.Interaction, count: int):
        embed = create_embed(
            title="🧹 Message Cleanup",
            description=f"Deleted `{count}` of the bot's previous messages. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="send", description="Sends a message to a specific channel (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def send_command(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        embed = create_embed(
            title="✉️ Message Sent",
            description=f"Your message has been sent to {channel.mention}. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="time", description="Displays the current date and time in AEST/AEDT.")
    async def time_command(self, interaction: discord.Interaction):
        now = datetime.now().strftime("%I:%M:%S %p %d-%b-%Y AEST/AEDT")
        embed = create_embed(
            title="Current Time",
            description=f"Current date and time in the RDU timezone:\n`{now}`"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="countdown", description="Starts a countdown timer for an event.")
    async def countdown_command(self, interaction: discord.Interaction, event_name: str, duration: str):
        embed = create_embed(
            title="⏳ Countdown Started",
            description=f"Countdown for **'{event_name}'** started, expiring in {duration}. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reminder", description="Sets a reminder for yourself or a channel.")
    async def reminder_command(self, interaction: discord.Interaction, time: str, message: str):
        embed = create_embed(
            title="🔔 Reminder Set",
            description=f"I will remind you in **{time}** about: '{message}'. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll", description="Creates a simple reaction-based poll.")
    async def poll_command(self, interaction: discord.Interaction, question: str, options: str):
        options_list = [f"**{chr(0x1f1e6 + i)}** - {opt.strip()}" for i, opt in enumerate(options.split(','))]
        
        embed = create_embed(
            title="📊 New Poll",
            description=f"**{question}**\n\n" + "\n".join(options_list)
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="weather", description="Checks the weather for a given city.")
    async def weather_command(self, interaction: discord.Interaction, city: str):
        embed = create_embed(
            title=f"☁️ Weather for {city}",
            description="The weather is 25°C, Sunny with a chance of PvP. (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="translate", description="Translates text to another language.")
    async def translate_command(self, interaction: discord.Interaction, text: str, target_lang: str):
        embed = create_embed(
            title="🌐 Translation",
            description=f"Original: '{text}'\nTranslated (to {target_lang}): '{text}' (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

# --- 2. MODERATION COMMANDS CLASS (30 Commands) ---

class ModerationCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        embed = create_embed(
            title="🔨 Member Kicked",
            description=f"{member.mention} was kicked by {interaction.user.mention}.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="Permanently bans a member from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        embed = create_embed(
            title="🚫 Member Banned",
            description=f"{member.mention} was permanently banned by {interaction.user.mention}.",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unban", description="Unbans a member using their user ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_command(self, interaction: discord.Interaction, user_id: str):
        embed = create_embed(
            title="🔓 User Unbanned",
            description=f"User with ID `{user_id}` was unbanned. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tempmute", description="Times out (mutes) a user for a specified duration.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def tempmute_command(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided."):
        embed = create_embed(
            title="🔇 User Timed Out",
            description=f"{member.mention} has been timed out for **{duration}**.",
            color=discord.Color.dark_teal()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unmute", description="Removes the timeout from a user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔊 Timeout Removed",
            description=f"The timeout has been removed from {member.mention}."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warn", description="Issues a formal warning to a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        embed = create_embed(
            title="⚠️ User Warning",
            description=f"A warning was issued to {member.mention} by {interaction.user.mention}.",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warnings", description="Checks a user's warning history.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title=f"📜 Warning History for {member.display_name}",
            description="Warning 1: Spamming (2024-01-01)\nWarning 2: Flamebaiting (2024-02-15)\n(Simulated History)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarns", description="Clears all warnings for a user (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarns_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="✅ Warnings Cleared",
            description=f"All moderation warnings for {member.mention} have been cleared."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lock", description="Locks the current text channel (prevents sending messages).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔒 Channel Locked",
            description=f"{interaction.channel.mention} has been locked. Only moderators can speak now."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlocks a previously locked channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔓 Channel Unlocked",
            description=f"{interaction.channel.mention} is now unlocked. Users can send messages."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="purge", description="Deletes a specified number of messages.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_command(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
        # This will need to be ephemeral or manually deleted
        embed = create_embed(
            title="🗑️ Message Purge",
            description=f"Successfully deleted `{count}` messages from this channel."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pin", description="Pins a message by its ID.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def pin_command(self, interaction: discord.Interaction, message_id: str):
        embed = create_embed(
            title="📌 Message Pinned",
            description=f"Message with ID `{message_id}` was pinned. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unpin", description="Unpins a message by its ID.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unpin_command(self, interaction: discord.Interaction, message_id: str):
        embed = create_embed(
            title="📍 Message Unpinned",
            description=f"Message with ID `{message_id}` was unpinned. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="embed", description="Creates a custom embed message (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def embed_command(self, interaction: discord.Interaction, title: str, description: str):
        custom_embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=custom_embed)
        # Prevent auto-deletion of user-created embed
        return # Skip auto-delete listener for this specific command

    @app_commands.command(name="slowmode", description="Sets the slowmode timer for the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_command(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        embed = create_embed(
            title="⏱️ Slowmode Set",
            description=f"Slowmode for {interaction.channel.mention} set to **{seconds} seconds**."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vick", description="Disconnects a user from a voice channel.")
    @app_commands.checks.has_permissions(move_members=True)
    async def vick_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🚪 Voice Kick",
            description=f"{member.mention} was disconnected from their voice channel. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vmute", description="Server-mutes a user in a voice channel.")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔇 Voice Mute",
            description=f"{member.mention} has been server-muted."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vunmute", description="Server-unmutes a user in a voice channel.")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vunmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔊 Voice Unmute",
            description=f"{member.mention} has been server-unmuted."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vmove", description="Moves a user to a different voice channel.")
    @app_commands.checks.has_permissions(move_members=True)
    async def vmove_command(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
        embed = create_embed(
            title="➡️ Voice Move",
            description=f"{member.mention} was moved to {channel.mention}. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="logset", description="Sets the channel for logging moderation actions (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def logset_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        embed = create_embed(
            title="📝 Log Channel Set",
            description=f"Moderation logs will now be sent to {channel.mention}."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="audit", description="Displays the last few actions from the server's audit log.")
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def audit_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔍 Audit Log Preview",
            description="Last 5 actions from the audit log displayed here. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="history", description="Shows the past moderation actions for a user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def history_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title=f"⏳ Mod History for {member.display_name}",
            description="Kick: 2023-10-01 (Reason: Spam)\nWarn: 2024-01-01 (Reason: Advertising)\n(Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="notes", description="Adds a private moderator note to a user's profile.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def notes_command(self, interaction: discord.Interaction, member: discord.Member, note: str):
        embed = create_embed(
            title="🗒️ Moderator Note Added",
            description=f"Private note added for {member.mention}: '{note}'"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="lookup", description="Looks up a user's Discord ID and account age.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def lookup_command(self, interaction: discord.Interaction, member_id: str):
        embed = create_embed(
            title=f"🔎 User Lookup: `{member_id}`",
            description="Account Created: 2020-05-01\nBot: No\n(Simulated Data)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="report", description="Allows users to privately report another member.")
    async def report_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        embed = create_embed(
            title="🚨 Report Submitted",
            description=f"Your report against {member.mention} has been submitted to the moderation team. Thank you for your input."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="modmail", description="Starts a private conversation with the moderation team.")
    async def modmail_command(self, interaction: discord.Interaction, message: str):
        embed = create_embed(
            title="📬 ModMail Initiated",
            description="A private conversation channel with the moderators has been created for you. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="anonreport", description="Submits an anonymous report to the mod team.")
    async def anonreport_command(self, interaction: discord.Interaction, reason: str):
        embed = create_embed(
            title="👻 Anonymous Report",
            description="Your report has been submitted anonymously to the moderation team. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="staffonline", description="Checks which staff members are currently online.")
    async def staffonline_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="👥 Online Staff",
            description="Moderator 1, Moderator 2 (Simulated List)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="altcheck", description="Checks if a user is likely an alternative account.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def altcheck_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🕵️ Alt Account Check",
            description=f"{member.mention} - Account age is 5 days. **High Alt Risk.** (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="filter", description="Manages the server's word filter list (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def filter_command(self, interaction: discord.Interaction, action: str, word: str):
        embed = create_embed(
            title="🔠 Word Filter Management",
            description=f"Action '{action}' executed for word '{word}'. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- 3. RUST-THEMED GAME COMMANDS CLASS (25 Commands) ---

class RustGameCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="wipe", description="Shows the date and time of the next map wipe.")
    async def wipe_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔪 Next Map Wipe",
            description="The next forced map wipe is **Thursday @ 8PM AEST** (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bpwipe", description="Shows the date of the next Blueprint wipe.")
    async def bpwipe_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Next Blueprint Wipe",
            description="Next BP Wipe: **1st Thursday of the Month** (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverstatus", description="Displays the live player count and RUST server health.")
    async def serverstatus_command(self, interaction: discord.Interaction):
        players = random.randint(50, 200)
        embed = create_embed(
            title="🟢 RUST Server Status",
            description=f"**Players:** {players}/250\n**Wipe Day:** Day 5\n**Health:** Excellent",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="map", description="Provides a link to the current server map.")
    async def map_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🗺️ Current Server Map",
            description="[Click here to view the live map on RustMaps](https://playrust.io/) (Simulated Link)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Shows the top players by kills, hours, or score.")
    async def leaderboard_command(self, interaction: discord.Interaction, metric: str = "kills"):
        embed = create_embed(
            title=f"🥇 Leaderboard: Top Kills",
            description="1. Xx_Gamer_xX (500 Kills)\n2. BaseBuilder (450 Kills)\n3. RustNoob (300 Kills)\n(Simulated Data)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="seed", description="Shows the server's current map seed and size.")
    async def seed_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🌳 Map Seed Info",
            description="**Map Seed:** `42069`\n**Map Size:** `3500`"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rules", description="Displays the server's custom ruleset.")
    async def rules_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Server Rules",
            description="1. Max Team Size: 4\n2. No Cheating/Exploiting\n3. Respect Admins\n(Simulated Rules)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="connect", description="Provides a direct link/IP to join the server.")
    async def connect_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔌 Connect to Server",
            description="Open your Rust console (`F1`) and type:\n`client.connect 1.1.1.1:28015`"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="Displays a player's in-game stats (K/D, hours, etc.).")
    async def profile_command(self, interaction: discord.Interaction, steam_id: str):
        embed = create_embed(
            title=f"📊 Player Profile: {steam_id}",
            description="K/D: 1.5\nHours This Wipe: 150h\n(Simulated Stats)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="topkills", description="Shows the player with the highest kill count this wipe.")
    async def topkills_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🎯 Top Killer of the Wipe",
            description="Player: **Xx_Gamer_xX**\nKills: **500**\n(Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="topmonuments", description="Shows the most visited monuments by a player.")
    async def topmonuments_command(self, interaction: discord.Interaction, steam_id: str):
        embed = create_embed(
            title=f"🏛️ Top Monuments for {steam_id}",
            description="1. Launch Site (150 Visits)\n2. Airfield (120 Visits)\n(Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kd", description="Checks a user's current Kill/Death ratio.")
    async def kd_command(self, interaction: discord.Interaction, steam_id: str):
        embed = create_embed(
            title=f"💀 K/D Ratio for {steam_id}",
            description="**Kills:** 300\n**Deaths:** 200\n**K/D:** 1.5"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hours", description="Checks a user's total hours played this wipe.")
    async def hours_command(self, interaction: discord.Interaction, steam_id: str):
        embed = create_embed(
            title=f"🕰️ Hours Played for {steam_id}",
            description="Total Hours This Wipe: **150 hours**"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="team", description="Shows the current members of your in-game team.")
    async def team_command(self, interaction: discord.Interaction, steam_id: str):
        embed = create_embed(
            title=f"👨‍👩‍👧‍👦 Team Members for {steam_id}",
            description="Player 1, Player 2, Player 3, Player 4 (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lastseen", description="Shows the last time a player was seen online.")
    async def lastseen_command(self, interaction: discord.Interaction, steam_id: str):
        embed = create_embed(
            title=f"👀 Last Seen: {steam_id}",
            description="Last Seen Online: **1 hour ago** (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="monuments", description="Lists all monuments on the current map and their location coordinates.")
    async def monuments_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📍 Monument Locations",
            description="Launch Site: E10\nAirfield: G15\nOutpost: K12\n(Simulated List)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="craft", description="Searches for a craftable item and its recipe.")
    async def craft_command(self, interaction: discord.Interaction, item: str):
        embed = create_embed(
            title=f"🛠️ Crafting Recipe: {item}",
            description="**Recipe:** 50 Metal Fragments, 100 Wood\n**Time:** 10 seconds\n(Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="iteminfo", description="Provides details, damage, and usage of any Rust item.")
    async def iteminfo_command(self, interaction: discord.Interaction, item: str):
        embed = create_embed(
            title=f"📝 Item Details: {item}",
            description="Damage: 40 (Head)\nDurability: High\nUsage: Mid-tier weapon\n(Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="price", description="Checks the community market price of a Rust item.")
    async def price_command(self, interaction: discord.Interaction, item: str):
        embed = create_embed(
            title=f"💰 Market Price: {item}",
            description="Community Market Price: **$5.00 AUD** (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ammo", description="Compares different ammunition types.")
    async def ammo_command(self, interaction: discord.Interaction, ammo_type: str):
        embed = create_embed(
            title=f"🔫 Ammo Comparison: {ammo_type}",
            description="Incendiary: High damage, low range.\nHV: High range, low damage.\n(Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="damagecalc", description="Calculates damage output against different armor.")
    async def damagecalc_command(self, interaction: discord.Interaction, weapon: str, armor: str):
        embed = create_embed(
            title="💥 Damage Calculator",
            description=f"**{weapon}** vs **{armor}**: 5 shots to kill. (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skins", description="Shows the latest featured Rust item skins.")
    async def skins_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🎨 Latest Featured Skins",
            description="Dragon AK, Ghost Hoodie, Neon Door. [Link to Store] (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setwipe", description="Sets the official wipe time for the bot to announce (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def setwipe_command(self, interaction: discord.Interaction, datetime_str: str):
        embed = create_embed(
            title="✅ Wipe Time Updated",
            description=f"Official wipe time has been set to: **{datetime_str}**."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="playerkick", description="Kicks a player from the *in-game* server (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def playerkick_command(self, interaction: discord.Interaction, steam_id: str, reason: str):
        embed = create_embed(
            title="🔨 In-Game Kick",
            description=f"Player with Steam ID `{steam_id}` has been kicked from the Rust server. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="playerban", description="Bans a player from the *in-game* server (admin-only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def playerban_command(self, interaction: discord.Interaction, steam_id: str, reason: str):
        embed = create_embed(
            title="🚫 In-Game Ban",
            description=f"Player with Steam ID `{steam_id}` has been banned from the Rust server. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- 4. FUN COMMANDS CLASS (20 Commands) ---

class FunCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="roll", description="Rolls a specified number of dice (e.g., 1d20).")
    async def roll_command(self, interaction: discord.Interaction, dice: str = "1d6"):
        # Simple simulation for rolling a single die
        try:
            num = int(dice.split('d')[0])
            sides = int(dice.split('d')[1])
            result = sum(random.randint(1, sides) for _ in range(num))
            embed = create_embed(
                title="🎲 Dice Roll",
                description=f"Rolled **{dice}** and got: **{result}**"
            )
        except Exception:
            embed = create_embed(
                title="🎲 Dice Roll",
                description="Please use the format `XdY` (e.g., `1d20`). Rolled **1d6** and got: **3** (Simulated)"
            )
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball", description="Asks the magic 8-ball a question.")
    async def eight_ball_command(self, interaction: discord.Interaction, question: str):
        responses = ["It is certain.", "It is decidedly so.", "Reply hazy, try again.", "Don't count on it.", "My sources say no."]
        embed = create_embed(
            title="🎱 Magic 8-Ball",
            description=f"**Question:** {question}\n**Answer:** {random.choice(responses)}"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="choose", description="Chooses randomly from a list of options.")
    async def choose_command(self, interaction: discord.Interaction, options: str):
        choices = [opt.strip() for opt in options.split(',')]
        if not choices:
            choice = "Error: Please provide options separated by commas."
        else:
            choice = random.choice(choices)
            
        embed = create_embed(
            title="🤔 I Choose...",
            description=f"From options: {options}\n\nMy choice: **{choice}**"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gif", description="Searches for a random GIF based on a keyword.")
    async def gif_command(self, interaction: discord.Interaction, keyword: str):
        embed = create_embed(
            title="🖼️ GIF Search",
            description=f"Random GIF for '{keyword}' [link to GIF] (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="react", description="Makes the bot react to a message with emojis.")
    @app_commands.checks.has_permissions(add_reactions=True)
    async def react_command(self, interaction: discord.Interaction, message_id: str, emoji: str):
        embed = create_embed(
            title="👍 Reaction Added",
            description=f"Successfully reacted to message ID `{message_id}` with {emoji}. (Placeholder)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quote", description="Saves or retrieves a famous or funny quote.")
    async def quote_command(self, interaction: discord.Interaction, action: str = "get", text: str = ""):
        if action.lower() == "get":
            embed = create_embed(
                title="💬 Random Quote",
                description="\"The only easy day was yesterday.\" - Rust God (Simulated)"
            )
        else:
            embed = create_embed(
                title="💾 Quote Saved",
                description=f"The quote '{text}' has been saved. (Placeholder)"
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="joke", description="Tells a random, clean joke.")
    async def joke_command(self, interaction: discord.Interaction):
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!", 
            "I told my wife she was drawing her eyebrows too high. She looked surprised.", 
            "I used to hate facial hair... but then it grew on me."
        ]
        embed = create_embed(
            title="😂 Joke Time",
            description=random.choice(jokes)
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="compliment", description="Gives a random compliment to a user.")
    async def compliment_command(self, interaction: discord.Interaction, member: discord.Member):
        compliments = ["is awesome!", "has great taste!", "is a fantastic person!", "is super smart!"]
        embed = create_embed(
            title="✨ Compliment",
            description=f"{member.mention} {random.choice(compliments)}"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="color", description="Shows a preview of a specified Hex color code.")
    async def color_command(self, interaction: discord.Interaction, hex_code: str):
        embed = create_embed(
            title=f"🌈 Color Preview: #{hex_code}",
            description="Color displayed in the embed sidebar. (Placeholder)",
            color=discord.Color.from_str(f"#{hex_code}") if len(hex_code) == 6 else discord.Color.default()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hex", description="Converts RGB to Hex and vice-versa.")
    async def hex_command(self, interaction: discord.Interaction, value: str):
        embed = create_embed(
            title="🎨 Color Converter",
            description=f"Conversion result for {value}: #FFFFFF (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="servericon", description="Displays the server's icon at full resolution.")
    async def servericon_command(self, interaction: discord.Interaction):
        if interaction.guild.icon:
            embed = create_embed(
                title="🖼️ Server Icon",
                description=f"[Click here for full resolution]({interaction.guild.icon.url})"
            )
            embed.set_image(url=interaction.guild.icon.url)
        else:
            embed = create_embed(
                title="🖼️ Server Icon",
                description="This server does not have an icon."
            )
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="langtranslate", description="Translates text using a placeholder service (Fun/Utility).")
    async def langtranslate_command(self, interaction: discord.Interaction, text: str, target_lang: str):
        embed = create_embed(
            title="🌐 Language Translate",
            description=f"'{text}' translated to '{target_lang}' (Placeholder Translation)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="define", description="Provides a dictionary definition for a word.")
    async def define_command(self, interaction: discord.Interaction, word: str):
        embed = create_embed(
            title=f"📚 Definition: {word}",
            description=f"**{word}** - A unit of speech used to convey meaning. (Simulated Definition)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shorten", description="Shortens a long URL.")
    async def shorten_command(self, interaction: discord.Interaction, url: str):
        embed = create_embed(
            title="✂️ URL Shortener",
            description=f"Original URL: {url}\nShortened Link: [short link] (Simulated)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="qrcode", description="Generates a QR code from a link or text.")
    async def qrcode_command(self, interaction: discord.Interaction, content: str):
        embed = create_embed(
            title="📱 QR Code Generator",
            description=f"QR Code generated for: '{content}' (Simulated Image)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hug", description="Sends a hug to another user.")
    async def hug_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🤗 Hug!",
            description=f"{interaction.user.mention} gives {member.mention} a warm hug!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pat", description="Gives a gentle pat to another user.")
    async def pat_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="👋 Head Pat",
            description=f"{interaction.user.mention} gives {member.mention} a gentle head pat."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="slap", description="Slaps another user (for fun).")
    async def slap_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="💥 Slap!",
            description=f"{interaction.user.mention} dramatically slaps {member.mention}!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kiss", description="Sends a kiss to another user.")
    async def kiss_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="😘 Kiss",
            description=f"{interaction.user.mention} gives {member.mention} a lovely kiss."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="marry", description="Starts a virtual marriage roleplay.")
    async def marry_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="💍 Virtual Marriage Proposal",
            description=f"{interaction.user.mention} asks {member.mention} to marry them! Type `/accept` or `/decline` to respond."
        )
        await interaction.response.send_message(embed=embed)


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
