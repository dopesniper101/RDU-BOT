import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging for DM attempts
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_dm_attempt(user, command_name):
    """Log DM command attempts"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"DM ATTEMPT - User: {user.name}#{user.discriminator} (ID: {user.id}) tried command: /{command_name} at {timestamp}"
    logger.warning(log_message)
    print(f"⚠️  {log_message}")

# Bot configuration
BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"

# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents, description=DESCRIPTION)

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
    """Welcome new members"""
    channel = discord.utils.get(member.guild.channels, name='welcome')
    if channel:
        embed = discord.Embed(
            title="Welcome to RUST DOWN UNDER!",
            description=f"G'day {member.mention}! Welcome to the server mate! 🇦🇺",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        await channel.send(embed=embed)

@bot.tree.command(name="ping", description="Check if the bot is responsive")
async def ping(interaction: discord.Interaction):
    """Ping command to test bot responsiveness"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "ping")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Display server information")
async def serverinfo(interaction: discord.Interaction):
    """Show server information"""
    guild = interaction.guild
    if not guild:
        log_dm_attempt(interaction.user, "serverinfo")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title=f"Server Info: {guild.name}",
        color=discord.Color.orange()
    )
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
            await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Unable to get user information!", ephemeral=True)
            return
        user = interaction.user
    
    embed = discord.Embed(
        title=f"User Info: {user.display_name}",
        color=discord.Color.purple()
    )
    embed.add_field(name="Username", value=f"{user.name}#{user.discriminator}", inline=True)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Joined Server", value=user.joined_at.strftime("%B %d, %Y") if user.joined_at else "Unknown", inline=True)
    embed.add_field(name="Account Created", value=user.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="Roles", value=len(user.roles) - 1, inline=True)  # -1 to exclude @everyone
    
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="testwelcome", description="Test the welcome message")
async def testwelcome(interaction: discord.Interaction):
    """Test what the welcome message looks like"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "testwelcome")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="Welcome to RUST DOWN UNDER!",
        description=f"G'day {interaction.user.mention}! Welcome to the server mate! 🇦🇺",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(text="This is a preview of the welcome message new members will see")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    """Display help information"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "help")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title=f"{BOT_NAME} - Available Commands",
        description="Here are the commands you can use:",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="General Commands", 
        value="""
        `/ping` - Check bot responsiveness
        `/serverinfo` - Show server information
        `/userinfo` - Show user information
        `/testwelcome` - Test the welcome message
        `/help` - Show this help message
        """, 
        inline=False
    )
    
    embed.add_field(
        name="Moderation Commands", 
        value="""
        `/kick` - Kick a user from the server
        `/ban` - Ban a user from the server
        `/mute` - Mute a user
        """, 
        inline=False
    )
    
    embed.set_footer(text="Use slash commands (/) to interact with the bot")
    await interaction.response.send_message(embed=embed)

# Moderation Commands
@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.describe(user="The user to kick", reason="Reason for the kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    """Kick a user from the server"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "kick")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("You don't have permission to kick members!", ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("You can't kick someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        await user.kick(reason=f"Kicked by {interaction.user}: {reason}")
        embed = discord.Embed(
            title="User Kicked",
            description=f"{user.mention} has been kicked from the server.",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to kick this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(user="The user to ban", reason="Reason for the ban")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    """Ban a user from the server"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "ban")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You don't have permission to ban members!", ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("You can't ban someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        await user.ban(reason=f"Banned by {interaction.user}: {reason}")
        embed = discord.Embed(
            title="User Banned",
            description=f"{user.mention} has been banned from the server.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to ban this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@bot.tree.command(name="mute", description="Mute a user in the server")
@app_commands.describe(user="The user to mute", duration="Duration in minutes", reason="Reason for the mute")
async def mute(interaction: discord.Interaction, user: discord.Member, duration: int = 60, reason: str = "No reason provided"):
    """Mute a user for a specified duration"""
    if not interaction.guild:
        log_dm_attempt(interaction.user, "mute")
        await interaction.response.send_message("This bot only works in servers, not DMs!", ephemeral=True)
        return
        
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("You don't have permission to mute members!", ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("You can't mute someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        # Convert duration to timedelta
        from datetime import datetime, timedelta
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
        
        await user.timeout(timeout_until, reason=f"Muted by {interaction.user}: {reason}")
        embed = discord.Embed(
            title="User Muted",
            description=f"{user.mention} has been muted for {duration} minutes.",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to mute this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command!")
    else:
        print(f'Error: {error}')
        await ctx.send("An error occurred while processing the command.")

# Run the bot
async def main():
    """Main function to run the bot"""
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not discord_token:
        print("ERROR: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please add your Discord bot token to the environment secrets.")
        return
    
    try:
        await bot.start(discord_token)
    except discord.LoginFailure:
        print("ERROR: Invalid Discord bot token!")
    except Exception as e:
        print(f"ERROR: Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())