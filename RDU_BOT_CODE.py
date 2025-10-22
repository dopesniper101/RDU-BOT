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
    # The automatic deletion footer for public messages
    embed.set_footer(text="Auto-deleting in 30 seconds.")
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
        """Attempts to delete the interaction response after 30 seconds, unless it was ephemeral."""
        # Note: ephemeral responses cannot be fetched and will fail here, which is correct.
        
        # Explicitly skip auto-delete for user-created embeds (/embed and /poll commands)
        if interaction.command and interaction.command.name in ['embed', 'poll']:
             return

        try:
            # Fetch the actual message sent by the bot after the interaction response
            message = await interaction.original_response()
            # If the response is ephemeral, it will fail the fetch with NotFound, 
            # or the message object's flags will confirm it's ephemeral, which we also skip.
            if message.flags.ephemeral:
                return

            self.loop.create_task(delete_after_30s(message))
        except discord.errors.NotFound:
            # Original response was not found (likely ephemeral or already deleted)
            pass
        except Exception as e:
            logger.warning(f"Error scheduling message deletion: {e}")


    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Global error handler 
        response_description = "An unexpected error occurred."
        color = discord.Color.red()
        ephemeral_status = True # Default to ephemeral for errors
        
        # Unwrap CommandInvokeError to get the real exception
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, app_commands.MissingPermissions):
            response_description = f"You do not have the required permissions to run this command: **{', '.join(error.missing_permissions)}**."
        elif isinstance(error, app_commands.CommandNotFound):
            return # Ignore if command not found
        elif isinstance(error, discord.errors.NotFound) and error.code == 10062:
            # Handle the specific defer timeout error (Unknown interaction)
            response_description = "The command took too long to respond and timed out. Please try again."
            ephemeral_status = True
        elif isinstance(error, app_commands.MissingRole) or isinstance(error, app_commands.MissingAnyRole):
            response_description = "You do not have the required role to run this command."
        elif isinstance(error, app_commands.BotMissingPermissions):
            response_description = f"The bot is missing the following permissions: **{', '.join(error.missing_permissions)}**."
        elif isinstance(error, discord.errors.Forbidden):
            response_description = "I do not have the necessary permissions (role hierarchy or missing permissions) to perform that action on the target."
        else:
            # Log the error for internal debugging
            logger.error(f"App Command Error: {error.__class__.__name__}: {error} in command {interaction.command.name if interaction.command else 'unknown'}")


        error_embed = create_embed("❌ Command Error", response_description, color)
        error_embed.set_footer(text="Error message (will not auto-delete).") # Override auto-delete footer for errors
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=ephemeral_status)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=ephemeral_status)
        except Exception:
            pass
        
# --- 1. CORE COMMANDS CLASS (25 Commands) ---

class CoreCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="help", description="Displays a list of available commands.")
    async def help_command(self, interaction: discord.Interaction):
        # FIX: Defer immediately to avoid the 'Unknown interaction' timeout error (10062)
        await interaction.response.defer(ephemeral=True)
        
        help_embed = discord.Embed(
            title=f"RUST DOWN UNDER BOT Commands",
            description="Use `/` followed by a category name (e.g., `/core`) to see commands, or just type `/` to browse the full list.\n\n",
            color=discord.Color.gold()
        )

        # Helper function to generate command list string
        def get_command_list(cog: commands.Cog) -> str:
            commands_list = sorted([f"```/{cmd.name}```" for cmd in cog.get_app_commands()])
            if not commands_list:
                return "No commands in this category."
            # Join with spaces to keep lines short and use markdown backticks
            return " ".join(commands_list)


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

        help_embed.set_footer(text="This private message will not auto-delete.")
        await interaction.followup.send(embed=help_embed, ephemeral=True)


    @app_commands.command(name="ping", description="Checks the bot's current latency (lag) to Discord.")
    async def ping_command(self, interaction: discord.Interaction):
        # --- IMPLEMENTATION: REAL LATENCY ---
        latency = round(self.bot.latency * 1000)
        embed = create_embed(
            title="🏓 Pong!",
            description=f"Latency: `{latency}ms`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="uptime", description="Shows how long the bot has been running continuously.")
    async def uptime_command(self, interaction: discord.Interaction):
        # --- IMPLEMENTATION: REAL UPTIME ---
        delta = datetime.now() - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
        
        embed = create_embed(
            title="⏰ Bot Uptime",
            description=f"Running continuously for: `{uptime_str}`"
        )
        await interaction.response.send_message(embed=embed)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="invite", description="Provides the bot's invitation link (Placeholder).")
    async def invite_command(self, interaction: discord.Interaction):
        link = discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions.all(), scopes=("bot", "applications.commands"))
        embed = create_embed(
            title="🔗 Invite Me",
            description=f"Click [here]({link}) to add the bot to your server. (Placeholder: Custom link logic needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="status", description="Displays the bot's current health and connection status (Placeholder).")
    async def status_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🟢 Bot Status",
            description="The bot is operational and successfully connected to Discord. (Placeholder: Detailed health check needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="Shows general information about the bot (Placeholder).")
    async def info_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🤖 Bot Information",
            description=f"I am the official Discord bot for the **{BOT_NAME}** community. (Placeholder: Version info, developer details needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="settings", description="Opens the server configuration menu (mod-only) (Placeholder).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="⚙️ Server Settings",
            description="Server settings panel not implemented yet. (Placeholder: UI components needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Displays detailed information about the current server.")
    async def serverinfo_command(self, interaction: discord.Interaction):
        # --- IMPLEMENTATION: REAL SERVER INFO ---
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
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="serverstatus", description="Displays the health and statistics of the current Discord server.")
    async def serverstatus_command(self, interaction: discord.Interaction):
        # --- IMPLEMENTATION: REAL DISCORD SERVER STATUS ---
        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        
        # Get counts
        member_count = guild.member_count
        online_members = len([m for m in guild.members if m.status != discord.Status.offline])
        booster_count = guild.premium_subscription_count
        
        # Get features and verification
        verification_level = str(guild.verification_level).replace('VerificationLevel.', '').title()
        boost_tier = f"Tier {guild.premium_tier}" if guild.premium_tier else "None"
        
        # List enabled key features
        features = [f.replace('_', ' ').title() for f in guild.features if f in ['COMMUNITY', 'DISCOVERABLE', 'INVITE_SPLASH', 'VERIFIED', 'VIP_REGIONS']]
        features_list = "\n".join([f"• {f}" for f in features]) if features else "None"

        embed = create_embed(
            title=f"🟢 Discord Server Status: {guild.name}",
            description=f"**Status:** Operational\n**ID:** `{guild.id}`\n**Owner:** {guild.owner.mention}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="👥 Members", value=f"**Total:** {member_count}\n**Online:** {online_members}", inline=True)
        embed.add_field(name="✨ Boosts", value=f"**Tier:** {boost_tier}\n**Count:** {booster_count}", inline=True)
        embed.add_field(name="🛡️ Security", value=f"**Verification:** {verification_level}", inline=True)
        embed.add_field(name="🔑 Key Features", value=features_list, inline=False)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        await interaction.followup.send(embed=embed)
        # --- END IMPLEMENTATION ---
        
    @app_commands.command(name="userinfo", description="Shows detailed information about a specific user.")
    async def userinfo_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        # --- IMPLEMENTATION: REAL USER INFO ---
        member = member or interaction.user
        
        embed = create_embed(
            title=f"👤 User Info: {member.display_name}",
            description=f"**ID:** `{member.id}`\n**Joined Server:** {member.joined_at.strftime('%b %d, %Y')}\n**Account Created:** {member.created_at.strftime('%b %d, %Y')}"
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="avatar", description="Displays a user's profile picture at full resolution.")
    async def avatar_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        # --- IMPLEMENTATION: REAL AVATAR ---
        member = member or interaction.user
        
        embed = create_embed(
            title=f"🖼️ Avatar for {member.display_name}",
            description=f"[Click here for full resolution]({member.display_avatar.url})"
        )
        embed.set_image(url=member.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="roles", description="Lists all roles in the server and their IDs (Placeholder).")
    async def roles_command(self, interaction: discord.Interaction):
        roles_list = [f"**{role.name}** (`{role.id}`)" for role in interaction.guild.roles if role.name != "@everyone"]
        
        embed = create_embed(
            title="🎭 Server Roles",
            description="\n".join(roles_list[:10]) + (f"\n...and {len(roles_list) - 10} more." if len(roles_list) > 10 else "") + "\n(Placeholder: Full pagination needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channels", description="Lists all channels in the server (Placeholder).")
    async def channels_command(self, interaction: discord.Interaction):
        text_channels = [c.name for c in interaction.guild.text_channels]
        voice_channels = [c.name for c in interaction.guild.voice_channels]
        
        embed = create_embed(
            title="💬 Server Channels",
            description="List of channels displayed here. (Placeholder: Detailed channel list needed)"
        )
        embed.add_field(name="Text Channels", value=f"`{len(text_channels)}` total", inline=True)
        embed.add_field(name="Voice Channels", value=f"`{len(voice_channels)}` total", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="boosters", description="Lists the server's nitro boosters (Placeholder).")
    async def boosters_command(self, interaction: discord.Interaction):
        boosters = interaction.guild.premium_subscribers
        booster_names = [b.display_name for b in boosters]
        
        embed = create_embed(
            title=f"✨ Nitro Boosters ({len(boosters)})",
            description="\n".join(booster_names) if booster_names else "No active boosters."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="joinrole", description="Sets the role new members automatically receive (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def joinrole_command(self, interaction: discord.Interaction, role: discord.Role):
        embed = create_embed(
            title="✅ Join Role Set",
            description=f"The automatic role for new members has been set to {role.mention}. (Placeholder: Database update needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sync", description="[Admin/Manager Only] Globally syncs all slash commands (Placeholder).")
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

    @app_commands.command(name="reload", description="Reloads a specific cog (owner-only) (Placeholder).")
    @commands.is_owner()
    async def reload_command(self, interaction: discord.Interaction, cog_name: str):
        embed = create_embed(
            title="🔄 Cog Reload",
            description=f"Attempting to reload cog `{cog_name}`... (Placeholder: Real reload logic needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="shutdown", description="Safely shuts down the bot (owner-only) (Placeholder).")
    @commands.is_owner()
    async def shutdown_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🛑 Shutting Down",
            description="Bot is initiating a safe shutdown. Goodbye!"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.bot.close()

    @app_commands.command(name="cleanup", description="Deletes a set number of the bot's previous messages (Placeholder).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cleanup_command(self, interaction: discord.Interaction, count: int):
        embed = create_embed(
            title="🧹 Message Cleanup",
            description=f"Deleted `{count}` of the bot's previous messages. (Placeholder: Custom message search needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="send", description="Sends a message to a specific channel (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def send_command(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        embed = create_embed(
            title="✉️ Message Sent",
            description=f"Your message has been sent to {channel.mention}. (Placeholder: Message sending needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="time", description="Displays the current date and time in AEST/AEDT (Placeholder).")
    async def time_command(self, interaction: discord.Interaction):
        # Using the current time based on the execution environment
        now = datetime.now().strftime("%I:%M:%S %p %d-%b-%Y AEST/AEDT")
        embed = create_embed(
            title="Current Time",
            description=f"Current date and time in the RDU timezone:\n`{now}` (Placeholder: Timezone conversion needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="countdown", description="Starts a countdown timer for an event (Placeholder).")
    async def countdown_command(self, interaction: discord.Interaction, event_name: str, duration: str):
        embed = create_embed(
            title="⏳ Countdown Started",
            description=f"Countdown for **'{event_name}'** started, expiring in {duration}. (Placeholder: Scheduling needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reminder", description="Sets a reminder for yourself or a channel (Placeholder).")
    async def reminder_command(self, interaction: discord.Interaction, time: str, message: str):
        embed = create_embed(
            title="🔔 Reminder Set",
            description=f"I will remind you in **{time}** about: '{message}'. (Placeholder: Scheduling needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="poll", description="Creates a simple reaction-based poll (Placeholder).")
    async def poll_command(self, interaction: discord.Interaction, question: str, options: str):
        options_list = [f"**{chr(0x1f1e6 + i)}** - {opt.strip()}" for i, opt in enumerate(options.split(','))]
        
        embed = discord.Embed(
            title="📊 New Poll",
            description=f"**{question}**\n\n" + "\n".join(options_list),
            color=discord.Color.purple()
        )
        # We skip the standard create_embed here to avoid the auto-delete footer,
        # and manually send a final response.
        await interaction.response.send_message(embed=embed)
        # Note: Reactions need to be added using interaction.original_response().add_reaction() after sending

    @app_commands.command(name="weather", description="Checks the weather for a given city (Placeholder).")
    async def weather_command(self, interaction: discord.Interaction, city: str):
        embed = create_embed(
            title=f"☁️ Weather for {city}",
            description="The weather is 25°C, Sunny with a chance of PvP. (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="translate", description="Translates text to another language (Placeholder).")
    async def translate_command(self, interaction: discord.Interaction, text: str, target_lang: str):
        embed = create_embed(
            title="🌐 Translation",
            description=f"Original: '{text}'\nTranslated (to {target_lang}): '{text}' (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="prefix", description="Changes the non-slash command prefix (Owner Only) (Placeholder).")
    @commands.is_owner()
    async def prefix_command(self, interaction: discord.Interaction, new_prefix: str):
        embed = create_embed(
            title="✏️ Prefix Changed",
            description=f"The non-slash command prefix has been set to `{new_prefix}`. (Placeholder: Database update needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="rules", description="Displays the server rules (Placeholder).")
    async def rules_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Server Rules",
            description="1. Be excellent to each other. 2. No cheating. 3. Follow Discord ToS. (Placeholder: Fetching from config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="faq", description="Find answers to frequently asked questions (Placeholder).")
    async def faq_command(self, interaction: discord.Interaction, topic: str):
        embed = create_embed(
            title=f"❓ FAQ: {topic.title()}",
            description="Answer for this topic is provided here. (Placeholder: Lookup logic needed)"
        )
        await interaction.response.send_message(embed=embed)
        

# --- 2. MODERATION COMMANDS CLASS (30 Commands) ---

class ModerationCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    def _check_hierarchy(self, moderator: discord.Member, target: discord.Member, action: str) -> Optional[str]:
        """Checks if the moderator and bot can perform the action on the target."""
        if target == moderator:
            return f"You cannot {action} yourself."
        
        # Check if moderator has a higher role than the target
        if moderator.top_role <= target.top_role and moderator != target.guild.owner:
            return f"You cannot {action} a member with an equal or higher role than you."
        
        # Check if bot has a higher role than the target
        if target.top_role >= target.guild.me.top_role:
             return f"I cannot {action} this member; my role is not high enough."
        
        return None

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        await interaction.response.defer(thinking=True)
        # --- IMPLEMENTATION: REAL KICK ---
        error_msg = self._check_hierarchy(interaction.user, member, "kick")
        if error_msg:
            embed = create_embed("❌ Error", error_msg, color=discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
             
        try:
            await member.kick(reason=reason)
            embed = create_embed(
                title="🔨 Member Kicked",
                description=f"{member.mention} (`{member.id}`) was kicked by {interaction.user.mention}.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.followup.send(embed=embed)
            
        except discord.errors.Forbidden:
             embed = create_embed("❌ Error", "I do not have the necessary permissions to kick this user.", color=discord.Color.red())
             await interaction.followup.send(embed=embed, ephemeral=True)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="ban", description="Permanently bans a member from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        await interaction.response.defer(thinking=True)
        # --- IMPLEMENTATION: REAL BAN ---
        error_msg = self._check_hierarchy(interaction.user, member, "ban")
        if error_msg:
            embed = create_embed("❌ Error", error_msg, color=discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
             
        try:
            await member.ban(reason=reason)
            embed = create_embed(
                title="🚫 Member Banned",
                description=f"{member.mention} (`{member.id}`) was permanently banned by {interaction.user.mention}.",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.followup.send(embed=embed)
            
        except discord.errors.Forbidden:
             embed = create_embed("❌ Error", "I do not have the necessary permissions to ban this user.", color=discord.Color.red())
             await interaction.followup.send(embed=embed, ephemeral=True)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="unban", description="Unbans a member using their user ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban_command(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(thinking=True)
        # --- IMPLEMENTATION: REAL UNBAN ---
        try:
            user = discord.Object(id=int(user_id))
            await interaction.guild.unban(user)

            embed = create_embed(
                title="🔓 User Unbanned",
                description=f"User with ID `{user_id}` was successfully unbanned.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except ValueError:
            embed = create_embed("❌ Error", "Invalid user ID provided. Must be a numeric ID.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.errors.NotFound:
            embed = create_embed("❌ Error", f"User with ID `{user_id}` is not currently banned on this server.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.errors.Forbidden:
            embed = create_embed("❌ Error", "I do not have permission to unban users.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="tempmute", description="Times out (mutes) a user for a specified duration (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def tempmute_command(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided."):
        embed = create_embed(
            title="🔇 User Timed Out",
            description=f"{member.mention} has been timed out for **{duration}**. (Placeholder: Time conversion needed)"
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unmute", description="Removes the timeout from a user (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔊 Timeout Removed",
            description=f"The timeout has been removed from {member.mention}. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warn", description="Issues a formal warning to a member (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        embed = create_embed(
            title="⚠️ User Warning",
            description=f"A warning was issued to {member.mention} by {interaction.user.mention}. (Placeholder: Database storage needed)"
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warnings", description="Checks a user's warning history (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title=f"📜 Warning History for {member.display_name}",
            description="Warning 1: Spamming (2024-01-01)\nWarning 2: Flamebaiting (2024-02-15)\n(Placeholder: Database query needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarns", description="Clears all warnings for a user (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarns_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="✅ Warnings Cleared",
            description=f"All moderation warnings for {member.mention} have been cleared. (Placeholder: Database deletion needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lock", description="Locks the current text channel (Placeholder).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔒 Channel Locked",
            description=f"{interaction.channel.mention} has been locked. (Placeholder: Permission update needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlocks a previously locked channel (Placeholder).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔓 Channel Unlocked",
            description=f"{interaction.channel.mention} is now unlocked. (Placeholder: Permission update needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="purge", description="Deletes a specified number of messages (max 100).")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def purge_command(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True, thinking=True)
        # --- IMPLEMENTATION: REAL PURGE ---
        
        deleted_count = 0
        try:
            deleted = await interaction.channel.purge(limit=count)
            deleted_count = len(deleted)
            
            embed = create_embed(
                title="🗑️ Message Purge Complete",
                description=f"Successfully deleted **{deleted_count}** messages from {interaction.channel.mention}.",
                color=discord.Color.gold()
            )
            embed.set_footer(text="This message is private and will not auto-delete.")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.errors.Forbidden:
             embed = create_embed("❌ Error", "I do not have the `Manage Messages` permission.", color=discord.Color.red())
             await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
             logger.error(f"Purge error: {e}")
             embed = create_embed("❌ Error", "An unexpected error occurred during message deletion.", color=discord.Color.red())
             await interaction.followup.send(embed=embed, ephemeral=True)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="pin", description="Pins a message by its ID (Placeholder).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def pin_command(self, interaction: discord.Interaction, message_id: str):
        embed = create_embed(
            title="📌 Message Pinned",
            description=f"Message with ID `{message_id}` was pinned. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unpin", description="Unpins a message by its ID (Placeholder).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unpin_command(self, interaction: discord.Interaction, message_id: str):
        embed = create_embed(
            title="📍 Message Unpinned",
            description=f"Message with ID `{message_id}` was unpinned. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="embed", description="Creates a custom embed message (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def embed_command(self, interaction: discord.Interaction, title: str, description: str):
        custom_embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )
        # This command is explicitly skipped by the auto-delete logic in on_app_command_completion
        await interaction.response.send_message(embed=custom_embed)

    @app_commands.command(name="slowmode", description="Sets the slowmode timer for the current channel (Placeholder).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_command(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        embed = create_embed(
            title="⏱️ Slowmode Set",
            description=f"Slowmode for {interaction.channel.mention} set to **{seconds} seconds**. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vick", description="Disconnects a user from a voice channel (Placeholder).")
    @app_commands.checks.has_permissions(move_members=True)
    async def vick_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🚪 Voice Kick",
            description=f"{member.mention} was disconnected from their voice channel. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vmute", description="Server-mutes a user in a voice channel (Placeholder).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔇 Voice Mute",
            description=f"{member.mention} has been server-muted. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vunmute", description="Server-unmutes a user in a voice channel (Placeholder).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vunmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔊 Voice Unmute",
            description=f"{member.mention} has been server-unmuted. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="vmove", description="Moves a user to a different voice channel (Placeholder).")
    @app_commands.checks.has_permissions(move_members=True)
    async def vmove_command(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
        embed = create_embed(
            title="➡️ Voice Move",
            description=f"{member.mention} was moved to {channel.mention}. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="logset", description="Sets the channel for logging moderation actions (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def logset_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        embed = create_embed(
            title="📝 Log Channel Set",
            description=f"Moderation logs will now be sent to {channel.mention}. (Placeholder: Config update needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="audit", description="Displays the last few actions from the server's audit log (Placeholder).")
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def audit_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔍 Audit Log Preview",
            description="Last 5 actions from the audit log displayed here. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="history", description="Shows the past moderation actions for a user (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def history_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title=f"⏳ Mod History for {member.display_name}",
            description="Kick: 2023-10-01 (Reason: Spam)\nWarn: 2024-01-01 (Reason: Advertising)\n(Placeholder: Database query needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="notes", description="Adds a private moderator note to a user's profile (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def notes_command(self, interaction: discord.Interaction, member: discord.Member, note: str):
        embed = create_embed(
            title="🗒️ Moderator Note Added",
            description=f"Note added for {member.mention}: '{note}' (Placeholder: Database storage needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="autorole", description="Configures the automatic role assignments (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_command(self, interaction: discord.Interaction, role: discord.Role):
        embed = create_embed(
            title="🤖 Autorole Configured",
            description=f"{role.mention} will now be assigned automatically. (Placeholder: Config update needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="filter", description="Manages the server's word filter list (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def filter_command(self, interaction: discord.Interaction, action: str, word: str):
        embed = create_embed(
            title="🚫 Word Filter Updated",
            description=f"Action '{action}' performed on word '{word}'. (Placeholder: Logic needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="inviteblock", description="Blocks specific invite links (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def inviteblock_command(self, interaction: discord.Interaction, domain: str):
        embed = create_embed(
            title="🔗 Invite Blocked",
            description=f"Invites from domain `{domain}` are now blocked. (Placeholder: Logic needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="tag", description="Creates or manages custom response tags (Placeholder).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def tag_command(self, interaction: discord.Interaction, name: str, content: Optional[str] = None):
        embed = create_embed(
            title="🏷️ Tag Managed",
            description=f"Tag `{name}` was created/updated/shown. (Placeholder: Database needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="report", description="Reports a member to the moderators (Placeholder).")
    async def report_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        embed = create_embed(
            title="🚨 Member Reported",
            description=f"{member.mention} reported for: '{reason}'. A moderator has been notified."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="ignore", description="Toggles bot response on a channel or user (admin-only) (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def ignore_command(self, interaction: discord.Interaction, target: discord.abc.GuildChannel | discord.Member):
        embed = create_embed(
            title="🤫 Ignore Toggled",
            description=f"Bot will now ignore messages from **{target.mention if isinstance(target, discord.Member) else target.name}**."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="banlist", description="Lists all currently banned users (Placeholder).")
    @app_commands.checks.has_permissions(ban_members=True)
    async def banlist_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Ban List",
            description="User A: Reason 1\nUser B: Reason 2\n(Placeholder: API call and pagination needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="massrole", description="Adds or removes a role from a large group of users (Placeholder).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def massrole_command(self, interaction: discord.Interaction, role: discord.Role, action: str):
        embed = create_embed(
            title="🎚️ Mass Role Action",
            description=f"Started process to {action} {role.mention} from applicable members. (Placeholder: Async process needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="nick", description="Changes a member's nickname (Placeholder).")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick_command(self, interaction: discord.Interaction, member: discord.Member, nickname: str):
        embed = create_embed(
            title="✏️ Nickname Changed",
            description=f"{member.mention}'s nickname set to **{nickname}**. (Placeholder: API call needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="clearnick", description="Resets a member's nickname (Placeholder).")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def clearnick_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="✏️ Nickname Cleared",
            description=f"{member.mention}'s nickname has been reset."
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="roleinfo", description="Displays detailed information about a role (Placeholder).")
    async def roleinfo_command(self, interaction: discord.Interaction, role: discord.Role):
        embed = create_embed(
            title=f"🎭 Role Info: {role.name}",
            description=f"**ID:** `{role.id}`\n**Members:** {len(role.members)}\n**Color:** {role.color}\n**Created:** {role.created_at.strftime('%b %d, %Y')}"
        )
        await interaction.response.send_message(embed=embed)


# --- 3. RUST-THEMED GAME COMMANDS CLASS (25 Commands) ---

class RustGameCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="wipe", description="Shows the date and time of the next map wipe (Placeholder).")
    async def wipe_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔪 Next Map Wipe",
            description="The next forced map wipe is **Thursday @ 8PM AEST** (Placeholder: Date calculation/config needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bpwipe", description="Shows the date of the next Blueprint wipe (Placeholder).")
    async def bpwipe_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Next Blueprint Wipe",
            description="Next BP Wipe: **1st Thursday of the Month** (Placeholder: Date calculation needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="servers", description="Lists all official RDU servers (Placeholder).")
    async def servers_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🌐 RDU Servers",
            description="RDU Main: IP\nRDU Mini: IP\n(Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="servermap", description="Shows the current map image for the main server (Placeholder).")
    async def servermap_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🗺️ Current Map",
            description="Map image URL here. (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="monuments", description="Lists key monuments on the current map (Placeholder).")
    async def monuments_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🏛️ Key Monuments",
            description="Launch Site, Military Tunnels, Oil Rig, etc. (Placeholder: Map API needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="events", description="Shows the current in-game event schedule (Placeholder).")
    async def events_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="💥 In-Game Events",
            description="Air Drop: TBD\nCargo Ship: TBD\n(Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="crafting", description="Shows the recipe for a specified item (Placeholder).")
    async def crafting_command(self, interaction: discord.Interaction, item: str):
        embed = create_embed(
            title=f"🛠️ Crafting: {item.title()}",
            description="Recipe: 50 Metal Fragments, 20 Low Grade Fuel. (Placeholder: Lookup needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="damage", description="Calculates weapon damage against armor (Placeholder).")
    async def damage_command(self, interaction: discord.Interaction, weapon: str, armor: str):
        embed = create_embed(
            title=f"🎯 Damage Calc: {weapon.title()} vs {armor.title()}",
            description="Headshot: 45 HP. Body Shot: 15 HP. (Placeholder: Calculation needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="resource", description="Checks the best way to farm a resource (Placeholder).")
    async def resource_command(self, interaction: discord.Interaction, resource: str):
        embed = create_embed(
            title=f"⛏️ Farming: {resource.title()}",
            description="Best Tool: Jackhammer. Best Monument: Quarry. (Placeholder: Lookup needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="teambox", description="Shares a team box code (Placeholder).")
    async def teambox_command(self, interaction: discord.Interaction, code: str):
        embed = create_embed(
            title="📦 Team Box Code",
            description=f"The team box combination is: `{code}`"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="market", description="Checks the prices for a marketplace item (Placeholder).")
    async def market_command(self, interaction: discord.Interaction, item: str):
        embed = create_embed(
            title=f"💰 Marketplace: {item.title()}",
            description="Current price: 100 Scrap. (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="giveaway", description="Starts a Rust item giveaway (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def giveaway_command(self, interaction: discord.Interaction, item: str, duration: str):
        embed = create_embed(
            title="🎁 Giveaway Started!",
            description=f"React to win **{item}**! Ends in {duration}."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kit", description="Displays the contents of a custom kit (Placeholder).")
    async def kit_command(self, interaction: discord.Interaction, kit_name: str):
        embed = create_embed(
            title=f"🎒 Kit: {kit_name.title()}",
            description="Contents: Full metal gear, AK, Meds. (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="steamid", description="Converts a username to a Steam ID (Placeholder).")
    async def steamid_command(self, interaction: discord.Interaction, username: str):
        embed = create_embed(
            title=f"🆔 Steam ID for {username}",
            description="Steam ID: `76561198xxxxxxxx` (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Shows the current server leaderboard (Placeholder).")
    async def leaderboard_command(self, interaction: discord.Interaction, stat: str):
        embed = create_embed(
            title=f"🥇 {stat.title()} Leaderboard",
            description="1. Player X (1000)\n2. Player Y (900)\n(Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="pvprate", description="Checks the server's PvP K/D ratio (Placeholder).")
    async def pvprate_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="⚔️ Server PvP Ratio",
            description="Server K/D: 1.25 (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ruleset", description="Displays the rules specific to the Rust server (Placeholder).")
    async def ruleset_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Rust Ruleset",
            description="No toxicity, no cheating, max team size 4. (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="uptimegame", description="Checks the Rust server's current uptime (Placeholder).")
    async def uptimegame_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="⏰ Rust Server Uptime",
            description="Running for: 3 days, 15 hours. (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="discordlink", description="Provides the Discord link for the server (Placeholder).")
    async def discordlink_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="💬 Discord Link",
            description="[Join our Discord!](https://discord.gg/RDU) (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="shop", description="Provides the link to the Rust store (Placeholder).")
    async def shop_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🛒 RDU Shop",
            description="[Support the Server!](http://shop.rdu.com) (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="teamspeak", description="Provides the Teamspeak details (Placeholder).")
    async def teamspeak_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🎙️ Teamspeak Info",
            description="Address: `ts.rdu.com` (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="patreon", description="Provides the Patreon link (Placeholder).")
    async def patreon_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="💖 Patreon Support",
            description="[Support RDU on Patreon!](http://patreon.com/RDU) (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="steamgroup", description="Provides the Steam Group link (Placeholder).")
    async def steamgroup_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="👥 Steam Group",
            description="[Join our Steam Group!](http://steamcommunity.com/groups/RDU) (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="twitter", description="Provides the Twitter link (Placeholder).")
    async def twitter_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🐦 Twitter",
            description="[Follow us on Twitter!](http://twitter.com/RDU) (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="youtube", description="Provides the YouTube link (Placeholder).")
    async def youtube_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🎥 YouTube",
            description="[Subscribe on YouTube!](http://youtube.com/RDU) (Placeholder: Config needed)"
        )
        await interaction.response.send_message(embed=embed)


# --- 4. FUN COMMANDS CLASS (20 Commands) ---

class FunCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="roll", description="Rolls a dice with a specified number of sides (Placeholder).")
    async def roll_command(self, interaction: discord.Interaction, sides: app_commands.Range[int, 2, 100] = 6):
        result = random.randint(1, sides)
        embed = create_embed(
            title="🎲 Dice Roll",
            description=f"You rolled a **{result}** on a D{sides}."
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="8ball", description="Ask the magic 8-Ball a question (Placeholder).")
    async def eightball_command(self, interaction: discord.Interaction, question: str):
        responses = ["Yes, definitely.", "It is decidedly so.", "Without a doubt.", "Reply hazy, try again.", "Ask again later.", "Don't count on it.", "My sources say no.", "Very doubtful."]
        response = random.choice(responses)
        embed = create_embed(
            title="🎱 Magic 8-Ball",
            description=f"**Q:** {question}\n**A:** {response}"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coinflip", description="Flips a coin (Placeholder).")
    async def coinflip_command(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        embed = create_embed(
            title="🪙 Coin Flip",
            description=f"The coin landed on **{result}**."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="choose", description="Chooses between multiple options (Placeholder).")
    async def choose_command(self, interaction: discord.Interaction, options: str):
        choices = [opt.strip() for opt in options.split(',') if opt.strip()]
        if len(choices) < 2:
            result = "Please provide at least two options separated by a comma."
        else:
            result = random.choice(choices)
        embed = create_embed(
            title="🤔 I Choose...",
            description=f"I choose **{result}**."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hug", description="Gives a virtual hug to a user (Placeholder).")
    async def hug_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🫂 Hug Time!",
            description=f"{interaction.user.mention} gives {member.mention} a warm hug!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="slap", description="Virtually slaps a user (Placeholder).")
    async def slap_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="✋ Slap!",
            description=f"{interaction.user.mention} slaps {member.mention} across the face!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="compliment", description="Gives a random compliment (Placeholder).")
    async def compliment_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        compliments = ["is awesome!", "has great taste!", "makes the server better!", "is a coding wizard!"]
        target = member.mention if member else interaction.user.mention
        embed = create_embed(
            title="✨ Compliment",
            description=f"{target} {random.choice(compliments)}"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dadjoke", description="Tells a terrible dad joke (Placeholder).")
    async def dadjoke_command(self, interaction: discord.Interaction):
        jokes = ["I'm afraid for the calendar. Its days are numbered.", "I told my wife she was drawing her eyebrows too high. She looked surprised.", "Why don't scientists trust atoms? Because they make up everything!"]
        embed = create_embed(
            title="😂 Dad Joke",
            description=random.choice(jokes)
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="meme", description="Posts a random meme (Placeholder).")
    async def meme_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🖼️ Random Meme",
            description="Meme image URL here. (Placeholder: Image fetch needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trivia", description="Starts a trivia game (Placeholder).")
    async def trivia_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🧠 Trivia Time",
            description="Question: What is the capital of Australia? (Placeholder: Game logic needed)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="scramble", description="Starts a word scramble game (Placeholder).")
    async def scramble_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🧩 Word Scramble",
            description="Unscramble this word: `RUTS` (Placeholder: Game logic needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="fight", description="Starts a virtual fight between two users (Placeholder).")
    async def fight_command(self, interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
        winner = random.choice([member1, member2])
        embed = create_embed(
            title="🥊 Fight!",
            description=f"{member1.mention} and {member2.mention} entered the arena. **{winner.mention}** wins!"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rate", description="Rates something on a scale of 1-10 (Placeholder).")
    async def rate_command(self, interaction: discord.Interaction, thing: str):
        rating = random.randint(1, 10)
        embed = create_embed(
            title="💯 Rating",
            description=f"I rate **{thing}** a **{rating}/10**."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ship", description="Calculates the compatibility between two users (Placeholder).")
    async def ship_command(self, interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
        compatibility = random.randint(1, 100)
        embed = create_embed(
            title="💘 Shipping",
            description=f"**{member1.display_name}** and **{member2.display_name}** are **{compatibility}%** compatible!"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="praise", description="Praises the bot (Placeholder).")
    async def praise_command(self, interaction: discord.Interaction):
        responses = ["Thank you! You're too kind.", "I live to serve.", "Praise accepted!"]
        embed = create_embed(
            title="😇 Praise",
            description=random.choice(responses)
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="roast", description="Roasts a user with a joke (Placeholder).")
    async def roast_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member.mention if member else "you"
        roasts = [f"{target} must have been born on a highway, because that's where most accidents happen.", f"I've had better arguments with a vending machine than with {target}.", f"{target}'s brain is 90% song lyrics and 10% trying to remember where they parked."]
        embed = create_embed(
            title="🔥 Roast",
            description=random.choice(roasts)
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="gif", description="Searches for a random GIF (Placeholder).")
    async def gif_command(self, interaction: discord.Interaction, search: str):
        embed = create_embed(
            title=f"🎬 GIF for '{search}'",
            description="GIF URL here. (Placeholder: External API needed)"
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="wyr", description="Ask a 'Would You Rather?' question (Placeholder).")
    async def wyr_command(self, interaction: discord.Interaction):
        questions = ["Would you rather be able to talk to animals or speak all foreign languages?", "Would you rather fight 100 duck-sized horses or one horse-sized duck?"]
        embed = create_embed(
            title="🤔 Would You Rather...",
            description=random.choice(questions)
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="unpopularopinion", description="Share an unpopular opinion anonymously (Placeholder).")
    async def unpopularopinion_command(self, interaction: discord.Interaction, opinion: str):
        embed = create_embed(
            title="📢 Unpopular Opinion",
            description=f"**Submitted by:** Anonymous\n\n> {opinion}",
            color=discord.Color.dark_orange()
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="confess", description="Submit an anonymous confession (Placeholder).")
    async def confess_command(self, interaction: discord.Interaction, confession: str):
        embed = create_embed(
            title="🤫 Anonymous Confession",
            description=f"> {confession}",
            color=discord.Color.light_grey()
        )
        await interaction.response.send_message(embed=embed)


# --- RUN BLOCK ---

if __name__ == '__main__':
    try:
        logger.info("Starting bot...")
        token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
        if not token:
            logger.error("Token missing. Cannot run.")

        bot = RDU_BOT()
        bot.run(token)
    except discord.errors.LoginFailure:
        logger.error("Failed to log in. Check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during bot execution: {e}")
