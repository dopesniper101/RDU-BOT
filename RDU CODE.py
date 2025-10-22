import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import logging
import random
from datetime import datetime, timedelta

# Set up standard logging (for terminal/console)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot configuration
BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs" # The name of the channel for logging all actions

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
            print(f"ERROR: Cannot send logs to #{LOG_CHANNEL_NAME} in {guild.name}. Check bot permissions.")
        except Exception as e:
            print(f"ERROR sending log: {e}")
    else:
        print(f"WARNING: Log channel '{LOG_CHANNEL_NAME}' not found in {guild.name}.")


def log_dm_attempt(user, command_name):
    """Log DM command attempts (console only)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"DM ATTEMPT - User: {user.name}#{user.discriminator} (ID: {user.id}) tried command: /{command_name} at {timestamp}"
    logger.warning(log_message)
    print(f"⚠️  {log_message}")

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    """Event triggered when the bot is ready"""
    print(f'{BOT_NAME} is now online!')
    print(f'Bot name: {bot.user}')
    print(f'Bot ID: {bot.user.id if bot.user else "Unknown"}')
    print('------')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.event
async def on_member_join(member):
    """Welcome new members and log the join"""
    # 1. Welcome Message
    welcome_channel = discord.utils.get(member.guild.channels, name='welcome') 
    if welcome_channel:
        embed = discord.Embed(
            title="Welcome to RUST DOWN UNDER!",
            description=f"G'day {member.mention}! Welcome to the server mate! 🇦🇺",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        await welcome_channel.send(embed=embed)

    # 2. Log Join (No moderator for auto-event)
    log_embed = discord.Embed(
        title="📥 Member Joined",
        description=f"{member.mention} ({member.id}) has joined the server.",
        color=discord.Color.blue()
    )
    log_embed.add_field(name="Account Created", value=f"{member.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}", inline=False)
    log_embed.set_footer(text=f"Total Members: {member.guild.member_count}")
    await send_log_embed(member.guild, log_embed)

@bot.event
async def on_member_remove(member):
    """Log when a member leaves (No moderator for auto-event)"""
    log_embed = discord.Embed(
        title="📤 Member Left",
        description=f"{member.name}#{member.discriminator} ({member.id}) has left the server.",
        color=discord.Color.dark_grey()
    )
    log_embed.set_footer(text=f"Total Members: {member.guild.member_count}")
    await send_log_embed(member.guild, log_embed)

# --- MODERATION COMMANDS ---

@bot.tree.command(name="warn", description="Issue a formal warning to a user")
@app_commands.describe(user="The user to warn", reason="Reason for the warning")
@app_commands.checks.has_permissions(kick_members=True)
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    """Warn a user (Kick Members permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "warn")
        return
    
    # 1. Send warning confirmation to the channel (ephemeral)
    embed = discord.Embed(
        title="⚠️ User Warned",
        description=f"{user.mention} has received a formal warning.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # 2. Attempt to DM the user
    try:
        dm_embed = discord.Embed(
            title=f"⚠️ You have been warned in {interaction.guild.name}",
            description="This is a formal warning. Repeated violations may result in a mute, kick, or ban.",
            color=discord.Color.orange()
        )
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Moderator", value=interaction.user.display_name, inline=True)
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        print(f"Could not DM warning to {user.name}")

    # 3. Log the action
    log_embed = discord.Embed(
        title="⚠️ User Warned",
        description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
        color=discord.Color.orange()
    )
    await send_log_embed(interaction.guild, log_embed)

@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.describe(user="The user to kick", reason="Reason for the kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    """Kick a user from the server"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "kick")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Cannot Kick", description="You can't kick someone with a higher or equal role!", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return
    
    try:
        await user.kick(reason=f"Kicked by {interaction.user.display_name}: {reason}")
        
        # 1. Send confirmation embed to channel
        embed = discord.Embed(title="✅ User Kicked", description=f"{user.mention} has been kicked from the server.", color=discord.Color.red())
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
        
        # 2. Log the action
        log_embed = discord.Embed(title="🔨 Member Kicked", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.red())
        await send_log_embed(interaction.guild, log_embed)
        
    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to kick this user!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="❌ System Error", description=f"An error occurred: {e}", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(user="The user to ban", reason="Reason for the ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    """Ban a user from the server"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "ban")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Cannot Ban", description="You can't ban someone with a higher or equal role!", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return
    
    try:
        await user.ban(reason=f"Banned by {interaction.user.display_name}: {reason}")
        
        # 1. Send confirmation embed to channel
        embed = discord.Embed(title="✅ User Banned", description=f"{user.mention} has been banned from the server.", color=discord.Color.dark_red())
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
        
        # 2. Log the action
        log_embed = discord.Embed(title="🚫 Member Banned", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.dark_red())
        await send_log_embed(interaction.guild, log_embed)
        
    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to ban this user!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="❌ System Error", description=f"An error occurred: {e}", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user using their Discord ID")
@app_commands.describe(user_id="The ID of the user to unban", reason="Reason for the unban")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    """Unban a user by ID (Ban Members permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "unban")
        return

    try:
        user = await bot.fetch_user(user_id)
        await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user.display_name}: {reason}")
        
        # 1. Send confirmation embed
        embed = discord.Embed(
            title="✅ User Unbanned",
            description=f"{user.name}#{user.discriminator} (ID: `{user_id}`) has been unbanned.",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🔓 Member Unbanned",
            description=f"**User:** {user.name} ({user.id})\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
            color=discord.Color.green()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.NotFound:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"User with ID `{user_id}` not found in the server's ban list.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ System Error",
            description=f"An error occurred during unban: {e}",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="mute", description="Mute a user in the server (same as /timeout)")
@app_commands.describe(user="The user to mute", duration="Duration in minutes (e.g., 60 for 1 hour)", reason="Reason for the mute")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, user: discord.Member, duration: int = 60, reason: str = "No reason provided"):
    """Mute a user for a specified duration"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "mute")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Cannot Mute", description="You can't mute someone with a higher or equal role!", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return
    
    try:
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
        
        await user.timeout(timeout_until, reason=f"Muted by {interaction.user.display_name}: {reason}")
        
        # 1. Send confirmation embed to channel
        embed = discord.Embed(title="✅ User Muted", description=f"{user.mention} has been muted for {duration} minutes.", color=discord.Color.yellow())
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🔇 Member Muted",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Duration:** {duration} minutes\n**Reason:** {reason}",
            color=discord.Color.yellow()
        )
        await send_log_embed(interaction.guild, log_embed)
        
    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to mute this user!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="❌ System Error", description=f"An error occurred: {e}", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="timeout", description="Time out (mute) a user for a duration")
@app_commands.describe(user="The user to timeout", duration_minutes="Duration in minutes (e.g., 60 for 1 hour)", reason="Reason for the timeout")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_user(interaction: discord.Interaction, user: discord.Member, duration_minutes: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
    """Timeout a user (Moderate Members permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "timeout")
        return
        
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Cannot Timeout", description="You can't timeout someone with a higher or equal role!", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return
    
    try:
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration_minutes)
        
        await user.timeout(timeout_until, reason=f"Timed out by {interaction.user.display_name}: {reason}")
        
        # 1. Send confirmation embed
        embed = discord.Embed(title="✅ User Timed Out", description=f"{user.mention} has been timed out for **{duration_minutes} minutes**.", color=discord.Color.yellow())
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🔇 Member Timed Out",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Duration:** {duration_minutes} minutes\n**Reason:** {reason}",
            color=discord.Color.yellow()
        )
        await send_log_embed(interaction.guild, log_embed)
        
    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to timeout this user!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="❌ System Error", description=f"An error occurred: {e}", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="untimeout", description="Removes an active timeout/mute from a user")
@app_commands.describe(user="The user to remove timeout from", reason="Reason for removing the timeout")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    """Remove timeout/mute from a user (Moderate Members permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "untimeout")
        return
        
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Cannot Untimeout", description="You can't remove timeout from someone with a higher or equal role!", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return
    
    if user.timeout is None:
        error_embed = discord.Embed(title="❌ Error", description=f"{user.mention} is not currently timed out.", color=discord.Color.red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    try:
        await user.timeout(None, reason=f"Timeout removed by {interaction.user.display_name}: {reason}")
        
        # 1. Send confirmation embed
        embed = discord.Embed(title="✅ Timeout Removed", description=f"Timeout/mute removed from {user.mention}.", color=discord.Color.green())
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🔊 Timeout Removed",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
            color=discord.Color.green()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to remove the timeout from this user!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="❌ System Error", description=f"An error occurred: {e}", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="clear", description="Clear a number of messages")
@app_commands.describe(amount="The number of messages to clear (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    """Clear messages (Manage Messages permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "clear")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    deleted = await interaction.channel.purge(limit=amount)
    
    # 1. Send confirmation embed
    embed = discord.Embed(title="🧹 Messages Cleared", description=f"Successfully deleted **{len(deleted)}** messages.", color=discord.Color.orange())
    await interaction.followup.send(embed=embed, ephemeral=True)
    
    # 2. Log the action
    log_embed = discord.Embed(
        title="🗑️ Messages Purged",
        description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**Amount:** {len(deleted)}",
        color=discord.Color.gold()
    )
    await send_log_embed(interaction.guild, log_embed)

@bot.tree.command(name="slowmode", description="Set the slowmode delay for the current channel")
@app_commands.describe(delay_seconds="Delay in seconds (0 to disable, max 21600)")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, delay_seconds: app_commands.Range[int, 0, 21600]):
    """Set slowmode (Manage Channels permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "slowmode")
        return
        
    try:
        await interaction.channel.edit(slowmode_delay=delay_seconds)
        
        if delay_seconds == 0:
            message = "Slowmode has been **disabled** in this channel."
            color = discord.Color.green()
        else:
            message = f"Slowmode has been set to **{delay_seconds} seconds**."
            color = discord.Color.orange()

        # 1. Send confirmation embed
        embed = discord.Embed(title="⏱️ Slowmode Updated", description=message, color=color)
        embed.set_footer(text=f"By {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="⏱️ Slowmode Change",
            description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**Delay:** {delay_seconds} seconds",
            color=color
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to manage channels!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)

@bot.tree.command(name="lock", description="Lock the current channel (prevent @everyone from sending messages)")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    """Lock channel (Manage Channels permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "lock")
        return

    try:
        # Get the default role (@everyone)
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        
        # Check if already locked
        if overwrite.send_messages is False:
            error_embed = discord.Embed(title="❌ Channel Already Locked", description="This channel is already locked.", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        # Set permissions to explicitly deny sending messages
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        # 1. Send confirmation embed
        embed = discord.Embed(title="🔒 Channel Locked", description="This channel is now restricted. Only authorized members can send messages.", color=discord.Color.dark_red())
        embed.set_footer(text=f"Locked by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**State:** Locked",
            color=discord.Color.dark_red()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to manage channel permissions!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock the current channel (allow @everyone to send messages)")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    """Unlock channel (Manage Channels permission required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "unlock")
        return

    try:
        # Get the default role (@everyone)
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        
        # Check if already unlocked (or neutral)
        if overwrite.send_messages is None or overwrite.send_messages is True:
            error_embed = discord.Embed(title="❌ Channel Not Locked", description="This channel is not explicitly locked.", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        # Set permissions to explicitly allow sending messages (or None to revert to default)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        # 1. Send confirmation embed
        embed = discord.Embed(title="🔓 Channel Unlocked", description="This channel is now public and anyone can send messages.", color=discord.Color.green())
        embed.set_footer(text=f"Unlocked by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**State:** Unlocked",
            color=discord.Color.green()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to manage channel permissions!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)

@bot.tree.command(name="addrole", description="Add a role to a user")
@app_commands.describe(user="The user to modify", role="The role to add")
@app_commands.checks.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    """Add a role to a user (Manage Roles permission required)"""
    if not interaction.guild:
        # Logged by the decorator if permissions fail in DM
        pass
    
    if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Role Hierarchy Error", description="You cannot manage a role higher than or equal to your own top role.", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return

    try:
        await user.add_roles(role)
        
        # 1. Send confirmation embed
        embed = discord.Embed(title="✅ Role Added", description=f"Added role {role.mention} to {user.mention}.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
        
        # 2. Log the action
        log_embed = discord.Embed(
            title="➕ Role Added",
            description=f"**User:** {user.mention}\n**Role:** {role.mention}\n**Moderator:** {interaction.user.mention}",
            color=discord.Color.green()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to manage that role.", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)

@bot.tree.command(name="removerole", description="Remove a role from a user")
@app_commands.describe(user="The user to modify", role="The role to remove")
@app_commands.checks.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    """Remove a role from a user (Manage Roles permission required)"""
    if not interaction.guild:
        # Logged by the decorator if permissions fail in DM
        pass
        
    if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        role_embed = discord.Embed(title="❌ Role Hierarchy Error", description="You cannot manage a role higher than or equal to your own top role.", color=discord.Color.red())
        await interaction.response.send_message(embed=role_embed, ephemeral=True)
        return

    try:
        await user.remove_roles(role)
        
        # 1. Send confirmation embed
        embed = discord.Embed(title="✅ Role Removed", description=f"Removed role {role.mention} from {user.mention}.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="➖ Role Removed",
            description=f"**User:** {user.mention}\n**Role:** {role.mention}\n**Moderator:** {interaction.user.mention}",
            color=discord.Color.dark_green()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to manage that role.", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)

@bot.tree.command(name="changenick", description="Change the nickname of a specified user")
@app_commands.describe(user="The user to change the nickname for", nickname="The new nickname (leave blank to clear)")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def changenick(interaction: discord.Interaction, user: discord.Member, nickname: str = None):
    """Change a user's nickname (Manage Nicknames required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "changenick")
        return

    # Check hierarchy
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        error_embed = discord.Embed(title="❌ Cannot Change Nickname", description="You cannot change the nickname of someone with a higher or equal role.", color=discord.Color.red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    old_nick = user.display_name
    new_nick = nickname if nickname else user.name

    try:
        await user.edit(nick=nickname, reason=f"Nickname changed by {interaction.user.display_name}")

        # 1. Send confirmation embed
        action = "cleared" if nickname is None else "changed"
        embed = discord.Embed(
            title="✅ Nickname Updated",
            description=f"{user.mention}'s nickname was **{action}**.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Old Nickname", value=old_nick, inline=True)
        embed.add_field(name="New Nickname", value=new_nick, inline=True)
        await interaction.response.send_message(embed=embed)

        # 2. Log the action
        log_embed = discord.Embed(
            title="👤 Nickname Change",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Old:** `{old_nick}`\n**New:** `{new_nick}`",
            color=discord.Color.blue()
        )
        await send_log_embed(interaction.guild, log_embed)

    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to change that user's nickname or the nickname is too high in the hierarchy.", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="❌ System Error", description=f"An error occurred: {e}", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)


# --- ADMIN/ANNOUNCEMENT COMMANDS ---

@bot.tree.command(name="say", description="Make the bot repeat a message")
@app_commands.describe(message="The message for the bot to repeat")
@app_commands.checks.has_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str):
    """Make the bot repeat a message (Admin only)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "say")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    await interaction.response.send_message("Message sent!", ephemeral=True)
    await interaction.channel.send(message)

    # Log the action
    log_embed = discord.Embed(
        title="🗣️ Bot Said",
        description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**Content:** {message[:1000]}{'...' if len(message) > 1000 else ''}",
        color=discord.Color.orange()
    )
    await send_log_embed(interaction.guild, log_embed)

@bot.tree.command(name="embed", description="Send a custom embed message to the current channel")
@app_commands.describe(title="Title of the embed", message="Main content of the embed", color_hex="Optional hex color code (e.g., #FF0000)")
@app_commands.checks.has_permissions(administrator=True)
async def embed_message(interaction: discord.Interaction, title: str, message: str, color_hex: str = "#FF5733"):
    """Send a custom embed (Administrator required)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "embed")
        return
        
    try:
        color = int(color_hex.lstrip('#'), 16)
    except ValueError:
        error_embed = discord.Embed(title="❌ Invalid Color", description="Please use a valid hex color code (e.g., `#00FF00`). Defaulting to a Rust color.", color=discord.Color.red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        color = 0xFF5733 # Default Rust color

    custom_embed = discord.Embed(
        title=title,
        description=message,
        color=color
    )
    custom_embed.set_footer(text=f"Posted by {interaction.user.display_name}")

    try:
        # Send the embed to the channel
        await interaction.response.send_message(embed=custom_embed)

        # Log the action
        log_embed = discord.Embed(
            title="📝 Custom Embed Sent",
            description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**Title:** {title}",
            color=discord.Color.dark_purple()
        )
        await send_log_embed(interaction.guild, log_embed)
    
    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to send embeds in this channel.", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=forbidden_embed, ephemeral=True)

@bot.tree.command(name="announcement", description="Post a styled announcement")
@app_commands.describe(title="The title of the announcement", message="The announcement message")
@app_commands.checks.has_permissions(administrator=True)
async def announcement(interaction: discord.Interaction, title: str, message: str):
    """Post a styled announcement (Admin only)"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "announcement")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)

    announcement_embed = discord.Embed(title=f"📢 {title}", description=message, color=discord.Color.red())
    announcement_embed.set_footer(text=f"Posted by {interaction.user.display_name}")

    try:
        await interaction.channel.send(embed=announcement_embed)
        
        # 1. Send confirmation embed
        success_embed = discord.Embed(title="✅ Announcement Sent", description="The announcement has been posted successfully.", color=discord.Color.green())
        await interaction.followup.send(embed=success_embed, ephemeral=True)

        # 2. Log the action
        log_embed = discord.Embed(
            title="🗣️ Announcement Made",
            description=f"**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}\n**Title:** {title}",
            color=discord.Color.red()
        )
        await send_log_embed(interaction.guild, log_embed)
        
    except discord.Forbidden:
        forbidden_embed = discord.Embed(title="❌ Bot Permission Error", description="I don't have permission to send messages in this channel.", color=discord.Color.dark_red())
        await interaction.followup.send(embed=forbidden_embed, ephemeral=True)

# --- UTILITY & FUN COMMANDS (No log needed for these) ---

@bot.tree.command(name="ping", description="Check if the bot is responsive")
async def ping(interaction: discord.Interaction):
    """Ping command to test bot responsiveness"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "ping")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Bot latency: {latency}ms", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Display server information")
async def serverinfo(interaction: discord.Interaction):
    """Show server information"""
    guild = interaction.guild
    if not guild:
        log_dm_attempt(interaction.user, "serverinfo")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.orange())
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Display user information")
@app_commands.describe(user="The user to get information about")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    """Show user information"""
    if user is None:
        if not interaction.guild:
            log_dm_attempt(interaction.user, "userinfo")
            dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
            await interaction.response.send_message(embed=dm_embed, ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            error_embed = discord.Embed(title="❌ Error", description="Unable to retrieve user information!", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        user = interaction.user
    
    embed = discord.Embed(title=f"User Info: {user.display_name}", color=discord.Color.purple())
    embed.add_field(name="Username", value=f"{user.name}#{user.discriminator}", inline=True)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Joined Server", value=user.joined_at.strftime("%B %d, %Y") if user.joined_at else "Unknown", inline=True)
    embed.add_field(name="Account Created", value=user.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="Roles", value=len(user.roles) - 1, inline=True)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="testwelcome", description="Test the welcome message")
async def testwelcome(interaction: discord.Interaction):
    """Test what the welcome message looks like"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "testwelcome")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    embed = discord.Embed(title="Welcome to RUST DOWN UNDER!", description=f"G'day {interaction.user.mention}! Welcome to the server mate! 🇦🇺", color=discord.Color.green())
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(text="This is a preview of the welcome message new members will see")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    """Display help information"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "help")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return
        
    embed = discord.Embed(title=f"{BOT_NAME} - Available Commands", description="Here are the commands you can use. All are slash commands (/).", color=discord.Color.gold())
    
    embed.add_field(name="General Commands", value="""/ping - Check bot responsiveness\n/serverinfo - Show server information\n/userinfo [user] - Show user information\n/testwelcome - Test the welcome message\n/avatar [user] - Get user's avatar\n/roll [sides] - Roll a die\n/coinflip - Flip a coin\n/8ball [q] - Get a prediction\n/invite - Get the bot's invite link\n/help - Show this help message""", inline=False)
    
    embed.add_field(name="Moderation & Admin Commands", value="""/warn [user] [reason]\n/kick [user] [reason]\n/ban [user] [reason]\n/unban [id] [reason]\n/timeout [user] [duration] [reason]\n/untimeout [user] [reason]\n/clear [amount]\n/addrole [user] [role]\n/removerole [user] [role]\n/changenick [user] [nick]\n/slowmode [seconds]\n/lock - Lock the channel\n/unlock - Unlock the channel\n/announcement [title] [msg]\n/embed [title] [msg] [color]\n/say [msg] - Bot repeats a message\n/checkperms [user] - Check user's channel permissions""", inline=False)
    
    embed.set_footer(text="Use slash commands (/) to interact with the bot")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Get the avatar of a specified user")
@app_commands.describe(user="The user whose avatar you want")
async def avatar(interaction: discord.Interaction, user: discord.Member = None):
    """Get user avatar"""
    user = user or interaction.user
    
    if not interaction.guild and user != interaction.user:
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="You can only check your own avatar in DMs, not others.", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return

    embed = discord.Embed(title=f"Avatar for {user.display_name}", color=discord.Color.blue())
    embed.set_image(url=user.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roll", description="Roll a die (default: 6 sides)")
@app_commands.describe(sides="Number of sides on the die (e.g., 20)", number="Number of dice to roll (default 1)")
async def roll(interaction: discord.Interaction, sides: int = 6, number: int = 1):
    """Roll a die"""
    if sides < 2 or number < 1 or number > 10:
        error_embed = discord.Embed(title="❌ Invalid Roll", description="Sides must be 2 or more. You can roll between 1 and 10 dice.", color=discord.Color.red())
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    results = [random.randint(1, sides) for _ in range(number)]
    total = sum(results)
    
    embed = discord.Embed(title="🎲 Dice Roll Results", description=f"Rolling {number}D{sides}...", color=discord.Color.purple())
    embed.add_field(name="Individual Rolls", value=", ".join(map(str, results)), inline=False)
    embed.add_field(name="Total", value=f"**{total}**", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="coinflip", description="Flip a coin: heads or tails")
async def coinflip(interaction: discord.Interaction):
    """Flip a coin"""
    result = random.choice(['Heads', 'Tails'])
    
    embed = discord.Embed(title="🪙 Coin Flip!", description=f"The coin landed on... **{result}**!", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="8ball", description="Ask the Magic 8-Ball a question")
@app_commands.describe(question="The question you want answered")
async def eightball(interaction: discord.Interaction, question: str):
    """Ask the Magic 8-Ball"""
    responses = ["It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.", "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.", "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."]
    answer = random.choice(responses)

    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.dark_gray())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=f"**{answer}**", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Get the bot's invite link")
async def invite(interaction: discord.Interaction):
    """Get the bot's invite link"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "invite")
        dm_embed = discord.Embed(title="🛑 Command Restricted", description="This command only works in servers, not DMs!", color=discord.Color.red())
        await interaction.response.send_message(embed=dm_embed, ephemeral=True)
        return

    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    
    embed = discord.Embed(title="🔗 Invite RUST DOWN UNDER Bot", description=f"Click the link below to invite the bot to your server!\n[Invite Link]({invite_url})", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="checkperms", description="Displays the permissions a user has in the current channel")
@app_commands.describe(user="The user to check permissions for")
async def checkperms(interaction: discord.Interaction, user: discord.Member = None):
    """Check user permissions in the current channel"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "checkperms")
        return
        
    user = user or interaction.user
    perms = interaction.channel.permissions_for(user)
    
    # Filter for granted permissions
    granted_perms = [
        f"✅ {name.replace('_', ' ').title()}" 
        for name, value in perms
        if value and not name.startswith("manage") # Exclude complex manage perms for brevity
    ]
    
    # Add a note about managing permissions
    if perms.manage_channels or perms.manage_roles or perms.manage_webhooks or perms.administrator:
        granted_perms.append("✅ **Advanced Management Permissions**")

    # Format output
    perms_list = "\n".join(granted_perms) if granted_perms else "None of the primary permissions are explicitly granted."

    embed = discord.Embed(
        title=f"Permissions for {user.display_name} in #{interaction.channel.name}",
        description=f"**User:** {user.mention}\n\n{perms_list}",
        color=discord.Color.teal()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Error Handling ---

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle slash command errors, especially permission checks."""
    if isinstance(error, app_commands.MissingPermissions) or isinstance(error, app_commands.MissingRole):
        permissions_needed = ', '.join(error.missing_permissions) if hasattr(error, 'missing_permissions') else str(error)
        
        perm_embed = discord.Embed(title="❌ Permission Denied", description=f"You do not have the required permissions to run this command.", color=discord.Color.red())
        perm_embed.add_field(name="Required Permissions", value=permissions_needed or "Administrator/Manage Roles/Messages", inline=False)
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=perm_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=perm_embed, ephemeral=True)
        return
    
    # Handle other unexpected errors
    error_embed = discord.Embed(title="❌ System Error", description=f"An unexpected error occurred: `{error}`", color=discord.Color.dark_red())
    if interaction.response.is_done():
        await interaction.followup.send(embed=error_embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    """Handle prefix command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        error_embed = discord.Embed(title="❌ Permission Denied", description="You don't have permission to use this command!", color=discord.Color.red())
        await ctx.send(embed=error_embed)
    else:
        print(f'Error: {error}')
        error_embed = discord.Embed(title="❌ Command Error", description="An unknown error occurred while processing the command.", color=discord.Color.dark_red())
        await ctx.send(embed=error_embed)

# --- RUN BOT ---

async def main():
    """Main function to run the bot"""
    
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not discord_token:
        discord_token = os.getenv('TOKEN')
    
    if not discord_token:
        print("\n🛑 ERROR: Discord bot token not found in environment variables.")
        print("Please ensure your token is added to Colab Secrets under the name 'DISCORD_BOT_TOKEN'.")
        return
    
    try:
        await bot.start(discord_token)
    except discord.LoginFailure:
        print("ERROR: Invalid Discord bot token! Please check your token.")
    except Exception as e:
        print(f"ERROR: Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
