# ==============================================================================
# 📝 RDU CODE.py Content (For GitHub)
# ==============================================================================
import os
import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
if not DISCORD_TOKEN:
    exit()

BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs" 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, description=DESCRIPTION, help_command=None)

async def send_log_embed(guild, embed):
    log_channel = discord.utils.get(guild.channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except Exception:
            pass

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass

@bot.tree.command(name="help", description="Shows a list of commands you have permission to use. (Ephemeral/30s)")
async def help_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in servers!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    allowed_commands = []
    
    for command in bot.tree.walk_commands():
        is_allowed = True
        
        if command._checks:
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
            title="Aussie RDU Bot Commands 🇦🇺",
            description=f"**Commands you can use in {interaction.guild.name}:**\n\n{commands_list}",
            color=discord.Color.gold()
        )
        embed.set_footer(text="This message is only visible to you and will self-dismiss after a short period (30s).")
    else:
        embed = discord.Embed(
            title="No Commands Available",
            description="You do not currently have permission to use any commands.",
            color=discord.Color.red()
        )
        embed.set_footer(text="This message is only visible to you and will self-dismiss after a short period (30s).")

    await interaction.followup.send(embed=embed, ephemeral=True)

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
        
try:
    bot.run(DISCORD_TOKEN)
except Exception:
    pass
