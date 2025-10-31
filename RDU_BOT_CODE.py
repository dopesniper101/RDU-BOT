# pip install discord

import os
import sys
import logging
from datetime import datetime
import asyncio
import random
from typing import Optional
import json
# END ADDED IMPORT

# Imports will now succeed because the Colab launcher guaranteed the installation
import discord
from discord.ext import commands
from discord import app_commands, utils
from discord.ext.commands import is_owner

# --- CONFIGURATION ---

# IMPORTANT: The Colab launcher sets this.
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
if not DISCORD_TOKEN:
    print("FATAL ERROR: Discord bot token not found in environment variables.")

BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
# Ensure you create a text channel with this exact name
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

        super().__init__(
            command_prefix='!',
            intents=intents,
            description=DESCRIPTION,
            help_command=None,
            owner_id=ADMIN_ID # Used for is_owner() check
        )
        self.start_time = datetime.now()
        self.log_channel_name = LOG_CHANNEL_NAME
        self.admin_id = ADMIN_ID
        self.log_channel = None # Initialize log channel object for global access
        
        # --- ADDITIONS FOR PERSISTENCE ---
        self.config_file = 'autodetect_config.json'
        config_data = self.load_config()
        # Auto-detection settings: {guild_id: {'keyword': str, 'justification': str, 'response': str}}
        self.detection_settings = config_data.get('detection_settings', {})
        # Warning settings: {guild_id: {user_id: [warning_record, ...]}}
        self.user_warnings = config_data.get('user_warnings', {})
        # --- END ADDITIONS ---

    # --- ADDED METHODS FOR CONFIG MANAGEMENT ---
    def load_config(self):
        """Loads all persistent settings from a file."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {self.config_file} not found. Starting with empty settings.")
            return {'detection_settings': {}, 'user_warnings': {}}
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            return {'detection_settings': {}, 'user_warnings': {}}

    def save_config(self):
        """Saves all persistent settings to a file."""
        try:
            save_data = {
                'detection_settings': self.detection_settings,
                'user_warnings': self.user_warnings
            }
            with open(self.config_file, 'w') as f:
                json.dump(save_data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
    # --- END ADDED METHODS ---


    async def setup_hook(self):
        """Called immediately before bot goes online to load cogs/classes."""

        # Add the monolithic command classes
        await self.add_cog(CoreCommands(self))
        await self.add_cog(ModerationCommands(self))
        await self.add_cog(FunCommands(self))
        await self.add_cog(AutoDetectCommands(self)) # ADDED NEW COG
        # Sync commands on startup
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} slash commands on startup.")
        except Exception as e:
            logger.error(f"Failed to sync commands on startup: {e}")


    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord! Latency: {round(self.latency * 1000)}ms')

        # Find the log channel across all guilds
        for guild in self.guilds:
            # Look for a channel with the specific name
            log_channel_candidate = discord.utils.get(guild.text_channels, name=self.log_channel_name)
            if log_channel_candidate:
                self.log_channel = log_channel_candidate
                logger.info(f"Found log channel: #{self.log_channel.name} in {guild.name}")
                break

        if not self.log_channel:
            logger.warning(f"Could not find the text channel named '{self.log_channel_name}' in any connected guild.")
        else:
            # Send a startup confirmation message to the log channel
            startup_embed = discord.Embed(
                title="✅ Bot Online",
                description=f"{self.user.name} is now operational. Latency: `{round(self.latency * 1000)}ms`.",
                color=discord.Color.green()
            )
            try:
                await self.log_channel.send(embed=startup_embed)
            except discord.errors.Forbidden:
                logger.error(f"Cannot send startup message to {self.log_channel.name}. Check bot permissions.")

    async def _log_action(self, title: str, description: str, moderator: discord.Member, target: Optional[discord.User | discord.Member | discord.Object] = None, color: discord.Color = discord.Color.blue()):
        """Central function to create and send embedded log messages to the bot-logs channel."""
        if not self.log_channel:
            logger.warning(f"Attempted to log action '{title}', but log channel is not configured.")
            return

        log_embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )

        # Add moderator/context details
        log_embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        if target:
            # Handle User objects (for unban) and Member objects (for kick/ban)
            if isinstance(target, discord.Member):
                log_embed.add_field(name="Target User", value=target.mention, inline=True)
                log_embed.add_field(name="Target ID", value=f"`{target.id}`", inline=True)
            elif isinstance(target, discord.Object) or isinstance(target, discord.User):
                # For unban where we only have ID
                log_embed.add_field(name="Target ID", value=f"`{target.id}`", inline=True)

        # Set footer for context and source
        log_embed.set_footer(text=f"Server: {moderator.guild.name} | Mod ID: {moderator.id}")

        try:
            await self.log_channel.send(embed=log_embed)
        except discord.errors.Forbidden:
            logger.error(f"Cannot send logs to {self.log_channel.name}. Check bot permissions in that channel.")
        except Exception as e:
            logger.error(f"Error sending log message: {e}")


    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Joined Guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command | app_commands.ContextMenu):
        """Attempts to delete the interaction response after 30 seconds, unless it was ephemeral or permanent."""

        # Skip auto-delete for commands intended to be permanent
        if interaction.command and interaction.command.name in ['poll', 'rules', 'faq']:
            return

        try:
            message = await interaction.original_response()

            # If the response is ephemeral, skip
            if message.flags.ephemeral:
                return

            self.loop.create_task(delete_after_30s(message))
        except discord.errors.NotFound:
            pass
        except Exception as e:
            logger.warning(f"Error scheduling message deletion: {e}")


    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Global error handler
        response_description = "An unexpected error occurred."
        color = discord.Color.red()
        ephemeral_status = True

        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        if isinstance(error, app_commands.MissingPermissions):
            response_description = f"You do not have the required permissions to run this command: **{', '.join(error.missing_permissions)}**."
        elif isinstance(error, app_commands.CommandNotFound):
            return
        elif isinstance(error, discord.errors.NotFound) and error.code == 10062:
            response_description = "The command took too long to respond and timed out. Please try again."
            ephemeral_status = True
        elif isinstance(error, app_commands.BotMissingPermissions):
            response_description = f"The bot is missing the following permissions: **{', '.join(error.missing_permissions)}**."
        elif isinstance(error, discord.errors.Forbidden):
            response_description = "I do not have the necessary permissions (role hierarchy or missing permissions) to perform that action on the target."
        elif isinstance(error, commands.NotOwner):
            response_description = "This command can only be run by the bot owner."
        else:
            logger.error(f"App Command Error: {error.__class__.__name__}: {error} in command {interaction.command.name if interaction.command else 'unknown'}")


        error_embed = create_embed("❌ Command Error", response_description, color)
        error_embed.set_footer(text="Error message (will not auto-delete).")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=ephemeral_status)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=ephemeral_status)
        except Exception:
            pass

    @commands.Cog.listener() # ADDED on_message LISTENER
    async def on_message(self, message):
        # Ignore messages from the bot itself and DMs
        if message.author == self.user or not message.guild:
            return

        # ADDED CHECKS: Ignore messages that are commands, bot responses, or thread messages
        if message.content.startswith('!') or message.type != discord.MessageType.default or message.is_system():
            return
        # END ADDED CHECKS

        guild_id = message.guild.id

        # Check if a detection rule is set for this server
        if guild_id in self.detection_settings:
            settings = self.detection_settings[guild_id]
            keyword = settings['keyword']
            response_template = settings['response']

            # Check if the keyword is in the message content (case-insensitive)
            if keyword in message.content.lower():

                # Customize the response (replace {server_id} with the actual ID)
                final_response = response_template.replace('{server_id}', str(guild_id))

                # CHANGED: Wrap the plain text response in an embed
                response_embed = discord.Embed(
                    title="🚨 Auto-Detection Triggered",
                    description=final_response,
                    color=discord.Color.red()
                )
                response_embed.set_footer(text=f"Rule: {settings['justification']}")
                # Send the customized response in the same channel as the message
                sent_message = await message.channel.send(embed=response_embed)
                
                # Auto-delete the response (assuming auto-delete is desired for auto-responses)
                self.loop.create_task(delete_after_30s(sent_message))
                # END CHANGED

        # Important: Process commands after the on_message logic
        await self.process_commands(message)


# --- 1. CORE COMMANDS CLASS ---

class CoreCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="help", description="Displays a list of available commands.")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        help_embed = discord.Embed(
            title=f"RUST DOWN UNDER BOT Commands",
            description="Use `/` to browse the full list of slash commands.\n\n",
            color=discord.Color.gold()
        )

        def get_command_list(cog: commands.Cog) -> str:
            commands_list = sorted([f"```/{cmd.name}```" for cmd in cog.get_app_commands()])
            # Also include traditional commands (for the new autodetect command)
            if cog.qualified_name == "AutoDetectCommands":
                commands_list.append("```!autodetect```")
            if not commands_list:
                return "No commands in this category."
            return " ".join(commands_list)

        core_cog = self.bot.get_cog("CoreCommands")
        mod_cog = self.bot.get_cog("ModerationCommands")
        fun_cog = self.bot.get_cog("FunCommands")
        autodetect_cog = self.bot.get_cog("AutoDetectCommands") # GET NEW COG

        help_embed.add_field(name="⚙️ Core Commands", value=get_command_list(core_cog), inline=False)
        help_embed.add_field(name="🛡️ Moderation Commands", value=get_command_list(mod_cog), inline=False)
        help_embed.add_field(name="🎉 Fun Commands", value=get_command_list(fun_cog), inline=False)
        help_embed.add_field(name="🤖 Auto-Response Commands", value=get_command_list(autodetect_cog), inline=False) # ADD NEW COG FIELD

        help_embed.set_footer(text="This private message will not auto-delete.")
        await interaction.followup.send(embed=help_embed, ephemeral=True)


    @app_commands.command(name="ping", description="Checks the bot's current latency (lag) to Discord.")
    async def ping_command(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = create_embed(
            title="🏓 Pong!",
            description=f"Latency: `{latency}ms`",
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

    @app_commands.command(name="sync", description="[Admin/Manager Only] Globally syncs all slash commands.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_guild=True)
    async def sync_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            synced = await self.bot.tree.sync()

            # Log the action
            await self.bot._log_action(
                title="🔄 Commands Synced",
                description=f"Successfully synced `{len(synced)}` commands globally.",
                moderator=interaction.user,
                color=discord.Color.blue()
            )

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

    @app_commands.command(name="shutdown", description="Safely shuts down the bot (owner-only).")
    @is_owner()
    async def shutdown_command(self, interaction: discord.Interaction):

        # Log the action
        await self.bot._log_action(
            title="🛑 Bot Shutting Down",
            description="Initiating safe shutdown sequence.",
            moderator=interaction.user,
            color=discord.Color.dark_red()
        )

        embed = create_embed(
            title="🛑 Shutting Down",
            description="Bot is initiating a safe shutdown. Goodbye!"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.bot.close()

    @app_commands.command(name="poll", description="Creates a simple reaction-based poll.")
    async def poll_command(self, interaction: discord.Interaction, question: str, options: str):
        await interaction.response.defer(thinking=True)

        options_list = [opt.strip() for opt in options.split(',')]

        # Poll validation logic (2 to 9 options)
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
        # Set footer to inform users it is permanent
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}. React to vote!")

        # Send the message
        await interaction.followup.send(embed=embed)

        # Add reactions
        message = await interaction.original_response()
        for emoji in reaction_emojis:
            await message.add_reaction(emoji)

    @app_commands.command(name="rules", description="Displays the server rules.")
    async def rules_command(self, interaction: discord.Interaction):
        # This will be permanent due to the listener exclusion
        embed = discord.Embed(
            title="📜 Server Rules",
            description="1. Be excellent to each other.\n2. No cheating or exploiting.\n3. Follow Discord ToS/Guidelines.\n4. Respect staff decisions.",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="faq", description="Find answers to frequently asked questions.")
    async def faq_command(self, interaction: discord.Interaction, topic: Optional[str] = "General"):
        # This will be permanent due to the listener exclusion
        embed = discord.Embed(
            title=f"❓ FAQ: {topic.title()}",
            description="This is the answer to your frequently asked question about this topic. (Content should be updated manually or fetched from a file/database in a real bot).",
            color=discord.Color.teal()
        )
        await interaction.response.send_message(embed=embed)


# --- 2. MODERATION COMMANDS CLASS ---

class ModerationCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    def _check_hierarchy(self, moderator: discord.Member, target: discord.Member, action: str) -> Optional[str]:
        """Checks if the moderator and bot can perform the action on the target."""
        if target == moderator:
            return f"You cannot {action} yourself."

        if moderator.top_role <= target.top_role and moderator != target.guild.owner:
            return f"You cannot {action} a member with an equal or higher role than you."

        if target.top_role >= target.guild.me.top_role:
            return f"I cannot {action} this member; my role is not high enough."

        return None

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        await interaction.response.defer(thinking=True)

        error_msg = self._check_hierarchy(interaction.user, member, "kick")
        if error_msg:
            embed = create_embed("❌ Error", error_msg, color=discord.Color.red())
            embed.set_footer(text="Error message (will not auto-delete).")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await member.kick(reason=reason)

            # Log the action
            await self.bot._log_action(
                title="🔨 Member Kicked",
                description=f"**Reason:** {reason}",
                moderator=interaction.user,
                target=member,
                color=discord.Color.orange()
            )

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

    @app_commands.command(name="ban", description="Permanently bans a member from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        await interaction.response.defer(thinking=True)

        error_msg = self._check_hierarchy(interaction.user, member, "ban")
        if error_msg:
            embed = create_embed("❌ Error", error_msg, color=discord.Color.red())
            embed.set_footer(text="Error message (will not auto-delete).")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await member.ban(reason=reason)

            # Log the action
            await self.bot._log_action(
                title="🚫 Member Banned",
                description=f"**Reason:** {reason}",
                moderator=interaction.user,
                target=member,
                color=discord.Color.red()
            )

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

    @app_commands.command(name="unban", description="Unbans a member using their user ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban_command(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(thinking=True)
        try:
            user_obj = discord.Object(id=int(user_id))
            await interaction.guild.unban(user_obj)

            # Log the action
            await self.bot._log_action(
                title="🔓 User Unbanned",
                description=f"User ID `{user_id}` has been unbanned.",
                moderator=interaction.user,
                target=user_obj, # CHANGED: Ensure the discord.Object is passed for logging
                color=discord.Color.green()
            )

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

    @app_commands.command(name="purge", description="Deletes a specified number of messages in the current channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def purge_command(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True, thinking=True)

        deleted = await interaction.channel.purge(limit=count)

        # Log the action
        await self.bot._log_action(
            title="🗑️ Messages Purged",
            description=f"Deleted **{len(deleted)}** messages in {interaction.channel.mention}.",
            moderator=interaction.user,
            color=discord.Color.dark_red()
        )

        embed = create_embed(
            title="🗑️ Messages Purged",
            description=f"Successfully deleted **{len(deleted)}** messages.",
            color=discord.Color.dark_red()
        )
        # Note: This is an ephemeral response.
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="lock", description="Locks a channel, preventing non-mod members from speaking.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def lock_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel

        overwrite = channel.overwrites_for(interaction.guild.default_role)
        if overwrite.send_messages is False:
            embed = create_embed("⚠️ Already Locked", f"{channel.mention} is already locked.", color=discord.Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        # Log the action
        await self.bot._log_action(
            title="🔒 Channel Locked",
            description=f"{channel.mention} has been locked.",
            moderator=interaction.user,
            color=discord.Color.red()
        )

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
        if overwrite.send_messages is None or overwrite.send_messages is True:
            embed = create_embed("⚠️ Already Unlocked", f"{channel.mention} is not explicitly locked.", color=discord.Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        overwrite.send_messages = None
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        # Log the action
        await self.bot._log_action(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} has been unlocked.",
            moderator=interaction.user,
            color=discord.Color.green()
        )

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

        # Log the action
        await self.bot._log_action(
            title="🐌 Slowmode Updated",
            description=f"{description}",
            moderator=interaction.user,
            color=discord.Color.blue()
        )

        # Response to the user
        embed = create_embed(
            title="🐌 Slowmode Updated",
            description=description,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    # --- ADDED COMMAND: WARN ---
    @app_commands.command(name="warn", description="Issues a formal warning to a member.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def warn_command(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        user_id_str = str(member.id)
        guild_id_str = str(interaction.guild.id)

        # 1. Initialize warnings if they don't exist for the user/guild
        if guild_id_str not in self.bot.user_warnings:
            self.bot.user_warnings[guild_id_str] = {}
        if user_id_str not in self.bot.user_warnings[guild_id_str]:
            self.bot.user_warnings[guild_id_str][user_id_str] = []

        # 2. Record the warning
        warning_record = {
            'timestamp': datetime.now().isoformat(),
            'moderator_id': interaction.user.id,
            'reason': reason
        }
        self.bot.user_warnings[guild_id_str][user_id_str].append(warning_record)

        # 3. Save the new state
        self.bot.save_config()

        # 4. Log the action
        await self.bot._log_action(
            title="⚠️ Member Warned",
            description=f"**Reason:** {reason}\n**Total Warnings:** {len(self.bot.user_warnings[guild_id_str][user_id_str])}",
            moderator=interaction.user,
            target=member,
            color=discord.Color.yellow()
        )

        # 5. Notify the user privately (if possible)
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ You Have Been Warned in {interaction.guild.name}",
                description=f"**Reason:** {reason}\nThis is warning **#{len(self.bot.user_warnings[guild_id_str][user_id_str])}**.",
                color=discord.Color.yellow()
            )
            await member.send(embed=dm_embed)
        except discord.errors.Forbidden:
            logger.warning(f"Could not DM warning to {member.name}.")

        # 6. Send public/ephemeral confirmation
        embed = create_embed(
            title="⚠️ Member Warned",
            description=f"{member.mention} was issued warning **#{len(self.bot.user_warnings[guild_id_str][user_id_str])}** by {interaction.user.mention}.",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)
    # --- END ADDED COMMAND ---


# --- 3. FUN COMMANDS CLASS ---

class FunCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @app_commands.command(name="dice", description="Rolls a virtual six-sided die.")
    async def dice_command(self, interaction: discord.Interaction):
        result = random.randint(1, 6)
        embed = create_embed(
            title="🎲 Dice Roll",
            description=f"You rolled a **{result}**!",
            color=discord.Color.dark_green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball", description="Ask the magic 8-Ball a question.")
    async def eightball_command(self, interaction: discord.Interaction, question: str):
        responses = [
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Yes - definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful."
        ]
        response = random.choice(responses)

        embed = create_embed(
            title="🎱 Magic 8-Ball",
            description=f"**Question:** {question}\n**Answer:** {response}",
            color=discord.Color.dark_grey()
        )
        await interaction.response.send_message(embed=embed)


# --- 4. AUTO-DETECT COMMANDS CLASS ---
# This is a new Cog for setting up a basic keyword auto-response system.

class AutoDetectCommands(commands.Cog):
    def __init__(self, bot: RDU_BOT):
        self.bot = bot

    @commands.command(name='autodetect', hidden=True) # Traditional command for setup/info
    @commands.is_owner()
    async def autodetect_legacy(self, ctx: commands.Context):
        """Hidden command to give instructions for the slash command to the owner."""
        # CHANGED: Ensure this legacy response is also an embed
        embed = discord.Embed(
            title="🤖 Auto-Response Setup",
            description="Please use the **`/autoreset`** or **`/autoset`** slash commands for configuration. This command is deprecated.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, delete_after=30)
        # END CHANGED

    @app_commands.command(name="autoset", description="[Admin Only] Sets a keyword auto-response for the server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def autoset_command(self, interaction: discord.Interaction, keyword: str, response: str, justification: str):
        # Enforce case-insensitivity on the stored keyword
        normalized_keyword = keyword.lower().strip()
        guild_id = interaction.guild.id

        if not normalized_keyword or not response:
            error_embed = create_embed("❌ Error", "Keyword and Response cannot be empty.", color=discord.Color.red())
            error_embed.set_footer(text="Error message (will not auto-delete).")
            return await interaction.response.send_message(embed=error_embed, ephemeral=True)

        # Store the new settings
        self.bot.detection_settings[guild_id] = {
            'keyword': normalized_keyword,
            'justification': justification,
            'response': response
        }
        # ADDED CONFIG SAVE
        self.bot.save_config()
        # END ADDED CONFIG SAVE

        # Log the action
        await self.bot._log_action(
            title="📝 Auto-Response SET",
            description=f"Auto-response rule created/updated for server.",
            moderator=interaction.user,
            color=discord.Color.purple()
        )

        embed = create_embed(
            title="✅ Auto-Response Set",
            description=f"**Keyword:** `{keyword}`\n**Response:** `{response}`\n**Justification:** {justification}",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Response will trigger when the keyword is mentioned (case-insensitive).")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="autoreset", description="[Admin Only] Removes the keyword auto-response for the server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def autoreset_command(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if guild_id in self.bot.detection_settings:
            del self.bot.detection_settings[guild_id]
            # ADDED CONFIG SAVE
            self.bot.save_config()
            # END ADDED CONFIG SAVE

            # Log the action
            await self.bot._log_action(
                title="🗑️ Auto-Response RESET",
                description="Auto-response rule removed for server.",
                moderator=interaction.user,
                color=discord.Color.dark_red()
            )

            embed = create_embed(
                title="✅ Auto-Response Reset",
                description="The keyword auto-response has been successfully removed for this server.",
                color=discord.Color.dark_red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = create_embed(
                title="⚠️ No Auto-Response Set",
                description="There is no active keyword auto-response to reset for this server.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# --- MAIN EXECUTION BLOCK ---

if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot = RDU_BOT()
        try:
            bot.run(DISCORD_TOKEN)
        except discord.LoginFailure:
            print("FATAL ERROR: Failed to log in. Check if the DISCORD_BOT_TOKEN is correct.")
        except KeyboardInterrupt:
            print("\nBot process interrupted by user. Shutting down...")
            sys.exit(0)
    else:
        print("Bot failed to start due to missing token.")
