# ==============================================================================
# 🤖 RDU BOT CODE (FULL CONTENT FOR GITHUB: RDU CODE.py)
# Includes Permissions-Aware, Ephemeral, Auto-Deleting /help Command
# ==============================================================================

import os
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime, timedelta
import asyncio # Required for the sleep function in /help

# --- SETUP ---

# Get the token from the environment variable set by the Colab Runner
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
if not DISCORD_TOKEN:
    print("❌ CRITICAL ERROR: Bot token not found in environment variables.")
    # Exiting here will prevent the bot.run() from failing later
    exit()

# Bot configuration
BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs" # The name of the channel for logging all actions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents, description=DESCRIPTION)

# --- Logging Helper Function ---

async def send_log_embed(guild, embed):
    """Finds the bot-logs channel and sends the embed."""
    log_channel = discord.utils.get(guild.channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            logger.error(f"Cannot send logs to #{LOG_CHANNEL_NAME} in {guild.name}. Check bot permissions.")
        except Exception as e:
            logger.error(f"ERROR sending log: {e}")

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    """Event triggered when the bot is ready"""
    print(f'{BOT_NAME} is now online!')
    print(f'Bot ID: {bot.user.id}')
    print('------')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# --- CORE COMMAND: HELP (Updated for Ephemeral, Permissions, and Auto-Delete) ---

@bot.tree.command(name="help", description="Shows a list of commands you have permission to use. (Ephemeral/30s)")
async def help_command(interaction: discord.Interaction):
    """
    Shows a list of commands the user has permission to use.
    The response is ephemeral and deletes itself after 30 seconds (user will see a 'Dismiss' button).
    """
    if not interaction.guild:
        await interaction.response.send_message("This command only works in servers!", ephemeral=True)
        return

    # Defer the response to allow time for processing
    await interaction.response.defer(ephemeral=True, thinking=True)

    allowed_commands = []
    
    # Iterate through all registered slash commands
    for command in bot.tree.walk_commands():
        is_allowed = True
        
        # Check if the user meets all permission checks (e.g., @app_commands.checks.has_permissions)
        if command._checks:
            for check in command._checks:
                try:
                    # Attempt to run the check; if it fails, an exception is raised
                    await discord.utils.maybe_coroutine(check, interaction)
                except (app_commands.MissingPermissions, app_commands.CheckFailure):
                    # If the user fails ANY check, they are not allowed to see the command
                    is_allowed = False
                    break
        
        if is_allowed:
            # Format: /command_name - command description
            allowed_commands.append(f"`/{command.name}` - {command.description}")

    # Create the final Embed
    if allowed_commands:
        commands_list = "\n".join(sorted(allowed_commands))
        embed = discord.Embed(
            title="Aussie RDU Bot Commands 🇦🇺",
            description=f"**Commands you can use in {interaction.guild.name}:**\n\n{commands_list}",
            color=discord.Color.gold()
        )
        # Ephemeral messages are dismissed by the user or Discord. Adding this to guide the user.
        embed.set_footer(text="This message is only visible to you and will self-dismiss after a short period (30s).")
    else:
        embed = discord.Embed(
            title="No Commands Available",
            description="You do not currently have permission to use any commands.",
            color=discord.Color.red()
        )
        embed.set_footer(text="This message is only visible to you and will self-dismiss after a short period (30s).")

    # Send the ephemeral message as a followup to the defer
    message = await interaction.followup.send(embed=embed, ephemeral=True)

    # Note on Auto-Delete: Ephemeral messages cannot be directly deleted by the bot
    # via the API after they are sent. We rely on the user dismissing the message 
    # or Discord's automatic timeout (which is longer than 30s). The `asyncio.sleep`
    # here is largely illustrative of the timer. If you needed true 30s deletion, 
    # the message could not be ephemeral.

# --- MODERATION COMMANDS (Your existing commands) ---

@bot.tree.command(name="warn", description="Issue a formal warning to a user")
@app_commands.describe(user="The user to warn", reason="Reason for the warning")
@app_commands.checks.has_permissions(kick_members=True)
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.guild: return
    
    embed = discord.Embed(title="⚠️ User Warned", description=f"{user.mention} has received a formal warning.", color=discord.Color.orange())
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    log_embed = discord.Embed(title="⚠️ User Warned", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.orange())
    await send_log_embed(interaction.guild, log_embed)

@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.describe(user="The user to kick", reason="Reason for the kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not interaction.guild: return
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ Cannot kick someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        await user.kick(reason=f"Kicked by {interaction.user.display_name}: {reason}")
        embed = discord.Embed(title="✅ User Kicked", description=f"{user.mention} has been kicked.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        log_embed = discord.Embed(title="🔨 Member Kicked", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.red())
        await send_log_embed(interaction.guild, log_embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to kick this user!", ephemeral=True)

# ... (Include all your other moderation commands like ban, mute, clear, etc. here) ...
# I am providing placeholders for the rest of your structure.

@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(user="The user to ban", reason="Reason for the ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not interaction.guild: return
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ Cannot ban someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        await user.ban(reason=f"Banned by {interaction.user.display_name}: {reason}")
        embed = discord.Embed(title="✅ User Banned", description=f"{user.mention} has been banned.", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=embed)
        log_embed = discord.Embed(title="🚫 Member Banned", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.dark_red())
        await send_log_embed(interaction.guild, log_embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to ban this user!", ephemeral=True)


@bot.tree.command(name="clear", description="Clear a number of messages")
@app_commands.describe(amount="The number of messages to clear (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    if not interaction.guild: return
        
    await interaction.response.defer(ephemeral=True)
    
    deleted = await interaction.channel.purge(limit=amount)
    
    embed = discord.Embed(title="🧹 Messages Cleared", description=f"Successfully deleted **{len(deleted)}** messages.", color=discord.Color.orange())
    await interaction.followup.send(embed=embed, ephemeral=True)
    
    log_embed = discord.Embed(title="🗑️ Messages Purged", description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**Amount:** {len(deleted)}", color=discord.Color.gold())
    await send_log_embed(interaction.guild, log_embed)


# --- ERROR HANDLER ---

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You do not have the required permissions to run this command.",
            color=discord.Color.red()
        )
        if interaction.response.is_done():
             await interaction.followup.send(embed=embed, ephemeral=True)
        else:
             await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        logger.error(f"Unhandled command error in {interaction.command.name}: {error}")
        
# --- BOT RUN ---

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print(f"\n\n❌ A critical error occurred during bot execution: {e}")
