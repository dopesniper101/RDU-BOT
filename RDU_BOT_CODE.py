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
from discord.ext.commands import is_owner # Used in owner checks

# --- CONFIGURATION ---

# IMPORTANT: The Colab launcher sets this.
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
if not DISCORD_TOKEN:
    print("FATAL ERROR: Discord bot token not found in environment variables.")

BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs"
# ⚠️ CRITICAL: REPLACE THIS WITH YOUR ACTUAL DISCORD USER ID 
ADMIN_ID = 123456789012345678 

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
        
        # 🟢 FIX: Pass ADMIN_ID as owner_id for owner-only checks to work
        super().__init__(
            command_prefix='!', 
            intents=intents, 
            description=DESCRIPTION, 
            help_command=None, 
            owner_id=ADMIN_ID
        )
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
        """Attempts to delete the interaction response after 30 seconds, unless it was ephemeral or permanent."""
        
        # 🟢 FIX: Explicitly skip auto-delete for permanent commands
        if interaction.command and interaction.command.name in ['poll', 'rules', 'faq', 'embed']: 
             return

        try:
            # Fetch the actual message sent by the bot after the interaction response
            message = await interaction.original_response()
            
            # If the response is ephemeral, skip
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
        elif isinstance(error, commands.NotOwner):
             response_description = "This command can only be run by the bot owner."
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
        # Permissions: Read/View, Send Messages, Embed Links, Read History, Use Slash Commands, Connect, Speak
        permissions = discord.Permissions(permissions=274877983744) 
        link = discord.utils.oauth_url(self.bot.user.id, permissions=permissions, scopes=("bot", "applications.commands"))
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
    @is_owner()
    async def reload_command(self, interaction: discord.Interaction, cog_name: str):
        embed = create_embed(
            title="🔄 Cog Reload",
            description=f"Attempting to reload cog `{cog_name}`... (Placeholder: Real reload logic needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="shutdown", description="Safely shuts down the bot (owner-only) (Placeholder).")
    @is_owner()
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
        # ⚠️ NOTE: The implementation to actually send the message to the channel is still needed here.
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

    @app_commands.command(name="poll", description="Creates a simple reaction-based poll.")
    async def poll_command(self, interaction: discord.Interaction, question: str, options: str):
        await interaction.response.defer(thinking=True) # Defer as we will be performing multiple async operations
        
        options_list = [opt.strip() for opt in options.split(',')]
        
        # 🟢 FIX: Poll validation logic (2 to 9 options)
        if not (2 <= len(options_list) <= 9):
            error_embed = create_embed("❌ Error", "A poll must have between 2 and 9 options (separated by commas).", color=discord.Color.red())
            error_embed.set_footer(text="Error message (will not auto-delete).")
            return await interaction.followup.send(embed=error_embed, ephemeral=True)
            
        # Define the A-J Unicode regional indicator emojis
        reaction_emojis = [chr(0x1f1e6 + i) for i in range(len(options_list))] # A, B, C...
        display_options = [f"**{reaction_emojis[i]}** - {opt}" for i, opt in enumerate(options_list)]
        
        embed = discord.Embed(
            title="📊 New Poll",
            description=f"**{question}**\n\n" + "\n".join(display_options),
            color=discord.Color.purple()
        )
        # 🟢 FIX: Set footer to inform users it is permanent
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}. React to vote!") 
        
        # Send the message
        await interaction.followup.send(embed=embed)
        
        # 🟢 FIX: Add reactions
        message = await interaction.original_response() 
        for emoji in reaction_emojis:
            await message.add_reaction(emoji)
            
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
    @is_owner()
    async def prefix_command(self, interaction: discord.Interaction, new_prefix: str):
        embed = create_embed(
            title="✏️ Prefix Changed",
            description=f"The non-slash command prefix has been set to `{new_prefix}`. (Placeholder: Database update needed)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="rules", description="Displays the server rules (Placeholder).")
    async def rules_command(self, interaction: discord.Interaction):
        # This will be permanent due to the listener exclusion
        embed = discord.Embed(
            title="📜 Server Rules",
            description="1. Be excellent to each other. 2. No cheating. 3. Follow Discord ToS. (Placeholder: Fetching from config needed)",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="faq", description="Find answers to frequently asked questions (Placeholder).")
    async def faq_command(self, interaction: discord.Interaction, topic: str):
        # This will be permanent due to the listener exclusion
        embed = discord.Embed(
            title=f"❓ FAQ: {topic.title()}",
            description="Answer for this topic is provided here. (Placeholder: Lookup logic needed)",
            color=discord.Color.teal()
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
            embed.set_footer(text="Error message (will not auto-delete).")
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
             embed.set_footer(text="Error message (will not auto-delete).")
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
            embed.set_footer(text="Error message (will not auto-delete).")
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
             embed.set_footer(text="Error message (will not auto-delete).")
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
            embed.set_footer(text="Error message (will not auto-delete).")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.errors.NotFound:
            embed = create_embed("❌ Error", f"User with ID `{user_id}` is not currently banned on this server.", color=discord.Color.red())
            embed.set_footer(text="Error message (will not auto-delete).")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.errors.Forbidden:
            embed = create_embed("❌ Error", "I do not have permission to unban users.", color=discord.Color.red())
            embed.set_footer(text="Error message (will not auto-delete).")
            await interaction.followup.send(embed=embed, ephemeral=True)
        # --- END IMPLEMENTATION ---

    @app_commands.command(name="mute", description="Mutes a member, restricting their ability to speak in voice/text (Placeholder).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def mute_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        embed = create_embed(
            title="🔇 Member Muted",
            description=f"{member.mention} was muted. (Placeholder: Role/Timeout logic needed)",
            color=discord.Color.dark_orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unmute", description="Unmutes a previously muted member (Placeholder).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def unmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔊 Member Unmuted",
            description=f"{member.mention} was unmuted. (Placeholder: Role/Timeout logic needed)",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="timeout", description="Applies a temporary timeout to a member (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_command(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided."):
        embed = create_embed(
            title="⏱️ Member Timed Out",
            description=f"{member.mention} was timed out for **{duration}**. (Placeholder: Time conversion needed)",
            color=discord.Color.dark_orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="remove_timeout", description="Removes a timeout from a member (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def remove_timeout_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="✅ Timeout Removed",
            description=f"Timeout removed for {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purge", description="Deletes a specified number of messages in the current channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def purge_command(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        deleted = await interaction.channel.purge(limit=count)
        
        embed = create_embed(
            title="🗑️ Messages Purged",
            description=f"Successfully deleted **{len(deleted)}** messages.",
            color=discord.Color.dark_red()
        )
        # Note: This is an ephemeral response, so we don't need the auto-delete task.
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    @app_commands.command(name="warn", description="Issues a formal warning to a member (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        embed = create_embed(
            title="⚠️ Warning Issued",
            description=f"Warning issued to {member.mention}.\n**Reason:** {reason} (Placeholder: Database logging needed)",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed) # Send publicly so others see the action

    @app_commands.command(name="warnings", description="Shows a member's warning history (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title=f"📜 Warnings for {member.display_name}",
            description="Member has 2 warnings. (Placeholder: Database lookup needed)",
            color=discord.Color.dark_grey()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear_warnings", description="Clears all warnings for a member (Placeholder).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clear_warnings_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="✅ Warnings Cleared",
            description=f"All warnings for {member.mention} have been cleared. (Placeholder: Database update needed)",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="lock", description="Locks a channel, preventing non-mod members from speaking.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = create_embed(
            title="🔒 Channel Locked",
            description=f"{channel.mention} has been locked. Only moderators can send messages.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlocks a channel, allowing non-mod members to speak.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def unlock_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None # Resets the explicit setting
        
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        
        embed = create_embed(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} has been unlocked. Members can send messages again.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="slowmode", description="Sets the slowmode delay for a channel (in seconds).")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def slowmode_command(self, interaction: discord.Interaction, delay: app_commands.Range[int, 0, 21600], channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        
        await channel.edit(slowmode_delay=delay)
        
        if delay == 0:
            description = f"Slowmode removed from {channel.mention}."
        else:
            description = f"Slowmode set to **{delay} seconds** in {channel.mention}."
            
        embed = create_embed(
            title="🐌 Slowmode Updated",
            description=description,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    # ... remaining Moderation Commands placeholders (addrole, removerole, nick, etc.)

    @app_commands.command(name="addrole", description="Gives a role to a member (Placeholder).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def addrole_command(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        embed = create_embed(
            title="➕ Role Added",
            description=f"Added {role.mention} to {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="removerole", description="Removes a role from a member (Placeholder).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole_command(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        embed = create_embed(
            title="➖ Role Removed",
            description=f"Removed {role.mention} from {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="nick", description="Changes a member's nickname (Placeholder).")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick_command(self, interaction: discord.Interaction, member: discord.Member, nickname: str):
        embed = create_embed(
            title="✏️ Nickname Changed",
            description=f"Changed {member.mention}'s nickname to **{nickname}**. (Placeholder: Implementation needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="vcmute", description="Server mutes a member in voice channels (Placeholder).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vcmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔇 Voice Muted",
            description=f"Voice muted {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.dark_orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="vcunmute", description="Server unmutes a member in voice channels (Placeholder).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def vcunmute_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔊 Voice Unmuted",
            description=f"Voice unmuted {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="vcdeafen", description="Server deafens a member in voice channels (Placeholder).")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def vcdeafen_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="🔕 Voice Deafened",
            description=f"Voice deafened {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.dark_orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="vcundeafen", description="Server undeafens a member in voice channels (Placeholder).")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def vcundeafen_command(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed(
            title="👂 Voice Undeafened",
            description=f"Voice undeafened {member.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="move", description="Moves a member to a different voice channel (Placeholder).")
    @app_commands.checks.has_permissions(move_members=True)
    async def move_command(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
        embed = create_embed(
            title="➡️ Member Moved",
            description=f"Moved {member.mention} to {channel.mention}. (Placeholder: Implementation needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="audit", description="Shows the server's audit log (Placeholder).")
    @app_commands.checks.has_permissions(view_audit_log=True)
    async def audit_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔎 Audit Log",
            description="Displaying recent audit log entries. (Placeholder: Log retrieval needed)",
            color=discord.Color.dark_grey()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="bulkdelete", description="Deletes messages matching a certain criteria (Placeholder).")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def bulkdelete_command(self, interaction: discord.Interaction, user: Optional[discord.Member], count: app_commands.Range[int, 1, 100]):
        embed = create_embed(
            title="🧹 Bulk Delete Initiated",
            description=f"Attempting to delete {count} messages from {'all users' if not user else user.mention}. (Placeholder: Message retrieval needed)",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="channelinfo", description="Shows detailed information about a specific channel (Placeholder).")
    async def channelinfo_command(self, interaction: discord.Interaction, channel: Optional[discord.abc.GuildChannel] = None):
        channel = channel or interaction.channel
        embed = create_embed(
            title=f"ℹ️ Channel Info: #{channel.name}",
            description=f"**ID:** `{channel.id}`\n**Type:** `{str(channel.type).replace('ChannelType.', '')}`\n**Created:** {channel.created_at.strftime('%b %d, %Y')}",
            color=discord.Color.light_grey()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="voiceinfo", description="Shows who is in a specific voice channel (Placeholder).")
    async def voiceinfo_command(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        members = [member.display_name for member in channel.members]
        embed = create_embed(
            title=f"🎤 Voice Info: {channel.name}",
            description=f"**Users Online:** {len(members)}\n**Members:** {', '.join(members) if members else 'None'}",
            color=discord.Color.dark_blue()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="temprole", description="Gives a role to a member for a specified time (Placeholder).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def temprole_command(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, duration: str):
        embed = create_embed(
            title="⏳ Temporary Role Added",
            description=f"Gave {role.mention} to {member.mention} for **{duration}**. (Placeholder: Scheduling needed)",
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="massrole", description="Adds a role to multiple members (Placeholder).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def massrole_command(self, interaction: discord.Interaction, role: discord.Role, condition: str):
        embed = create_embed(
            title="👥 Mass Role Update",
            description=f"Applying {role.mention} to members matching condition: **{condition}**. (Placeholder: Logic needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="logchannel", description="Sets the bot's logging channel (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def logchannel_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        embed = create_embed(
            title="📝 Log Channel Set",
            description=f"Bot logs will now be sent to {channel.mention}. (Placeholder: Configuration update needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="welcomechannel", description="Sets the channel for welcome messages (Placeholder).")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcomechannel_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        embed = create_embed(
            title="👋 Welcome Channel Set",
            description=f"Welcome messages will now be sent to {channel.mention}. (Placeholder: Configuration update needed)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- 3. RUST GAME COMMANDS CLASS (Placeholder) ---

class RustGameCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="wipe", description="Announces and tracks the next Rust wipe time (Placeholder).")
    async def wipe_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🔪 Next Wipe",
            description="The next forced wipe is on **Thurs, Oct 30th** at 5:00 PM AEST. (Placeholder: Dynamic calculation needed)",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server", description="Checks the status of the main RDU Rust server (Placeholder).")
    async def server_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🎮 Server Status",
            description="**RDU Main:** Online\n**Players:** 150/200\n**Map:** Procedural\n**IP:** `connect 1.1.1.1:28015` (Placeholder: RCON/API needed)",
            color=discord.Color.dark_green()
        )
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="map", description="Shows the current server map and seed (Placeholder).")
    async def map_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="🗺️ Current Map",
            description="**Map Seed:** 123456\n**Map Size:** 3500\n[View Map on RustMaps.com](https://placeholder.com) (Placeholder: API needed)",
            color=discord.Color.dark_green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rules_rust", description="Displays the Rust server-specific rules (Placeholder).")
    async def rules_rust_command(self, interaction: discord.Interaction):
        embed = create_embed(
            title="📜 Rust Server Rules",
            description="1. Max team size of 4. 2. No hacking. 3. No extreme toxicity. (Placeholder: Content needed)",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Shows the current leaderboards (Placeholder).")
    async def leaderboard_command(self, interaction: discord.Interaction, category: str):
        embed = create_embed(
            title=f"🏆 {category.title()} Leaderboard",
            description="1. PlayerX (100 Kills)\n2. PlayerY (90 Kills) (Placeholder: Database needed)",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

# --- 4. FUN COMMANDS CLASS (Placeholder) ---

class FunCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8-Ball a question.")
    async def eightball_command(self, interaction: discord.Interaction, question: str):
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
            "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."
        ]
        embed = create_embed(
            title="🎱 Magic 8-Ball",
            description=f"**Q:** {question}\n**A:** **{random.choice(responses)}**",
            color=discord.Color.dark_grey()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dice", description="Rolls a virtual dice.")
    async def dice_command(self, interaction: discord.Interaction, sides: app_commands.Range[int, 2, 100]):
        roll = random.randint(1, sides)
        embed = create_embed(
            title="🎲 Dice Roll",
            description=f"You rolled a **D{sides}** and got: **{roll}**",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coin", description="Flips a coin.")
    async def coin_command(self, interaction: discord.Interaction):
        flip = random.choice(["Heads", "Tails"])
        embed = create_embed(
            title="🪙 Coin Flip",
            description=f"The coin landed on: **{flip}**",
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ship", description="Calculates the compatibility of two members (Placeholder).")
    async def ship_command(self, interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
        compatibility = random.randint(0, 100)
        embed = create_embed(
            title="💘 Ship Calculator",
            description=f"**{member1.display_name}** and **{member2.display_name}** are **{compatibility}%** compatible!",
            color=discord.Color.magenta()
        )
        await interaction.response.send_message(embed=embed)


# --- BOT EXECUTION ---
if __name__ == "__main__":
    if DISCORD_TOKEN:
        try:
            bot = RDU_BOT()
            bot.run(DISCORD_TOKEN)
        except discord.LoginFailure:
            logger.critical("❌ Login Failure: The Discord token is invalid or incorrect.")
            sys.exit(1)
        except Exception as e:
            logger.critical(f"❌ Unhandled critical error: {e}")
            sys.exit(1)
    else:
        sys.exit(1)
