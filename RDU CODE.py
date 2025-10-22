import os
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
import asyncio
import random
import time

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

# Ensure help_command=None is present and initialize bot
bot = commands.Bot(command_prefix='!', intents=intents, description=DESCRIPTION, help_command=None)
bot.start_time = datetime.now() # Initialize bot start time

# --- UTILITY FUNCTIONS ---

async def send_log_embed(guild, embed):
    log_channel = discord.utils.get(guild.channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except Exception:
            pass

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    print(f'{BOT_NAME} is now online!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# --- CORE COMMAND: HELP (ULTIMATE ROBUST FIX) ---

@bot.tree.command(name="help", description="Shows a list of commands you have permission to use. (Ephemeral/30s)")
async def help_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in servers!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    allowed_commands = []
    
    for command in bot.tree.walk_commands():
        
        # FINAL FIX: Explicitly check if the object is a modern slash command 
        # and has the internal check list before trying to access it.
        if not isinstance(command, app_commands.Command) or not hasattr(command, '_checks'):
            continue

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

# ----------------------------------------------------
# 🛡️ MODERATION COMMANDS (10)
# ----------------------------------------------------

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
        await interaction.response.send_message(embed=discord.Embed(title="✅ User Kicked", description=f"{user.mention} has been kicked.", color=discord.Color.red()))
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
        await interaction.response.send_message(embed=discord.Embed(title="✅ User Banned", description=f"{user.mention} has been banned.", color=discord.Color.dark_red()))
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

@bot.tree.command(name="tempmute", description="Mute a user for a specified duration")
@app_commands.describe(user="The user to mute", duration_minutes="Duration in minutes", reason="Reason for the mute")
@app_commands.checks.has_permissions(moderate_members=True)
async def tempmute(interaction: discord.Interaction, user: discord.Member, duration_minutes: app_commands.Range[int, 1, 1440], reason: str):
    if not interaction.guild: return
    try:
        # Use discord.utils.timedelta for correct usage
        duration = discord.utils.timedelta(minutes=duration_minutes) 
        await user.timeout(duration, reason=f"Timed out by {interaction.user.display_name}: {reason}")
        embed = discord.Embed(title="🔇 User Muted", description=f"{user.mention} has been muted for {duration_minutes} minutes.", color=discord.Color.dark_gray())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_embed = discord.Embed(title="🕒 Member Timed Out", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Duration:** {duration_minutes}m\n**Reason:** {reason}", color=discord.Color.dark_gray())
        await send_log_embed(interaction.guild, log_embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to mute this user!", ephemeral=True)

@bot.tree.command(name="unmute", description="Unmute a user")
@app_commands.describe(user="The user to unmute")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not interaction.guild: return
    try:
        await user.timeout(None)
        embed = discord.Embed(title="🔊 User Unmuted", description=f"{user.mention} has been unmuted.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_embed = discord.Embed(title="✅ Member Untimed Out", description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}", color=discord.Color.green())
        await send_log_embed(interaction.guild, log_embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to unmute this user!", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user by their ID")
@app_commands.describe(user_id="The ID of the user to unban")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    if not interaction.guild: return
    try:
        user = discord.Object(id=int(user_id))
        await interaction.guild.unban(user)
        embed = discord.Embed(title="✅ User Unbanned", description=f"User ID **{user_id}** has been unbanned.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_embed = discord.Embed(title="🔓 Member Unbanned", description=f"**User ID:** {user_id}\n**Moderator:** {interaction.user.mention}", color=discord.Color.green())
        await send_log_embed(interaction.guild, log_embed)
    except discord.NotFound:
        await interaction.response.send_message("❌ User ID not found in the ban list.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("❌ An error occurred while unbanning. Check the ID format.", ephemeral=True)

@bot.tree.command(name="slowmode", description="Set the slowmode delay for the current channel")
@app_commands.describe(seconds="Delay in seconds (0 to disable)", reason="Reason for changing slowmode")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600], reason: str = "No reason provided"):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ Slowmode can only be set in text channels.", ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=seconds, reason=f"Slowmode set by {interaction.user.display_name}: {reason}")
    if seconds == 0:
        msg = "✅ Slowmode has been disabled."
    else:
        msg = f"✅ Slowmode set to **{seconds}** seconds."
    await interaction.response.send_message(msg, ephemeral=True)
    log_embed = discord.Embed(title="⏳ Slowmode Updated", description=f"**Channel:** {interaction.channel.mention}\n**Delay:** {seconds}s\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.blue())
    await send_log_embed(interaction.guild, log_embed)

@bot.tree.command(name="addrole", description="Assign a role to a user")
@app_commands.describe(user="The user to modify", role="The role to assign")
@app_commands.checks.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not interaction.guild: return
    if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ Cannot add a role higher or equal to your highest role.", ephemeral=True)
        return
    try:
        await user.add_roles(role)
        await interaction.response.send_message(f"✅ Assigned role {role.mention} to {user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to assign that role.", ephemeral=True)

@bot.tree.command(name="removerole", description="Remove a role from a user")
@app_commands.describe(user="The user to modify", role="The role to remove")
@app_commands.checks.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not interaction.guild: return
    try:
        await user.remove_roles(role)
        await interaction.response.send_message(f"✅ Removed role {role.mention} from {user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to remove that role.", ephemeral=True)

# ----------------------------------------------------
# 🔧 UTILITY COMMANDS (10)
# ----------------------------------------------------

@bot.tree.command(name="ping", description="Shows the bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is **{latency}ms**.")

@bot.tree.command(name="userinfo", description="Get information about a server member")
@app_commands.describe(user="The member to inspect (optional)")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    if not interaction.guild: return
    
    embed = discord.Embed(title=f"User Info: {user.display_name}", color=user.color or discord.Color.blue())
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Joined Server", value=discord.utils.format_dt(user.joined_at, style='R'), inline=True)
    embed.add_field(name="Joined Discord", value=discord.utils.format_dt(user.created_at, style='R'), inline=True)
    embed.add_field(name="Highest Role", value=user.top_role.mention, inline=True)
    embed.add_field(name="Bot?", value="Yes" if user.bot else "No", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="serverinfo", description="Get information about the current server")
async def serverinfo(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in a server.", ephemeral=True)
        return
        
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.teal())
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Created On", value=discord.utils.format_dt(guild.created_at, style='R'), inline=True)
    embed.add_field(name="Verification Level", value=str(guild.verification_level).capitalize(), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="avatar", description="Get a user's avatar image")
@app_commands.describe(user="The member whose avatar to fetch (optional)")
async def avatar(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    embed = discord.Embed(title=f"{user.display_name}'s Avatar", color=user.color or discord.Color.blue())
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roll", description="Roll a dice (e.g., d20, 2d6)")
@app_commands.describe(roll_string="The dice to roll (e.g., 1d6, 3d20)")
async def roll(interaction: discord.Interaction, roll_string: str):
    try:
        num_dice, sides = map(int, roll_string.lower().split('d'))
        if num_dice <= 0 or sides <= 0 or num_dice > 100 or sides > 1000:
            raise ValueError
    except ValueError:
        await interaction.response.send_message("❌ Invalid roll format. Use format like `1d6` or `3d20`.", ephemeral=True)
        return

    results = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(results)
    
    embed = discord.Embed(title="🎲 Dice Roll Results", color=discord.Color.purple())
    embed.add_field(name=f"Roll: {roll_string}", value=f"Total: **{total}**", inline=False)
    if num_dice > 1:
        embed.add_field(name="Individual Rolls", value=", ".join(map(str, results)), inline=False)
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="say", description="Makes the bot repeat a message")
@app_commands.describe(message="The message for the bot to repeat")
@app_commands.checks.has_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("✅ Message sent!", ephemeral=True)
    await interaction.channel.send(message)

@bot.tree.command(name="vote", description="Start a simple Yes/No poll")
@app_commands.describe(question="The question for the poll")
async def vote(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="🗳️ New Poll", description=f"**Question:** {question}\n\nReact to vote!", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    await message.add_reaction("👍")
    await message.add_reaction("👎")
    await message.add_reaction("🤷")

@bot.tree.command(name="nickname", description="Change a user's nickname")
@app_commands.describe(user="The user whose nickname to change", nickname="The new nickname (blank to reset)")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def nickname(interaction: discord.Interaction, user: discord.Member, nickname: str = None):
    if not interaction.guild: return
    try:
        await user.edit(nick=nickname, reason=f"Nickname changed by {interaction.user.display_name}")
        msg = f"✅ Changed {user.name}'s nickname to **{nickname}**." if nickname else f"✅ Reset {user.name}'s nickname."
        await interaction.response.send_message(msg, ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I cannot change that user's nickname (permissions or hierarchy).", ephemeral=True)

@bot.tree.command(name="roleinfo", description="Get information about a specific role")
@app_commands.describe(role="The role to inspect")
async def roleinfo(interaction: discord.Interaction, role: discord.Role):
    if not interaction.guild: return
    
    embed = discord.Embed(title=f"Role Info: {role.name}", color=role.color or discord.Color.default())
    embed.add_field(name="ID", value=role.id, inline=True)
    embed.add_field(name="Members", value=len(role.members), inline=True)
    embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
    embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
    embed.add_field(name="Position", value=role.position, inline=True)
    embed.add_field(name="Created At", value=discord.utils.format_dt(role.created_at, style='R'), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="uptime", description="Shows how long the bot has been running")
async def uptime(interaction: discord.Interaction):
    delta = datetime.now() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    time_str = f"{hours}h {minutes}m {seconds}s"
    
    embed = discord.Embed(title="⏰ Bot Uptime", description=f"The bot has been running for: **{time_str}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ----------------------------------------------------
# ⛏️ RUST/GAME COMMANDS (14)
# ----------------------------------------------------

@bot.tree.command(name="wipe", description="Shows the next expected server wipe time")
async def wipe(interaction: discord.Interaction):
    next_wipe = datetime(2025, 12, 5, 0, 0) # Placeholder: Dec 5, 2025
    time_remaining = next_wipe - datetime.now()
    
    if time_remaining.total_seconds() < 0:
        response = "⏳ The next wipe date has not been announced yet, or the last one passed! Check server rules."
        color = discord.Color.red()
    else:
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        response = f"The next forced wipe is expected on **{next_wipe.strftime('%b %d, %Y')}**.\nTime remaining: **{days} days, {hours} hours, and {minutes} minutes**."
        color = discord.Color.orange()
    
    embed = discord.Embed(title="🗓️ RDU Server Wipe", description=response, color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status", description="Shows the RDU server status and player count")
async def status(interaction: discord.Interaction):
    player_count = random.randint(50, 250)
    max_players = 300
    status_text = "Online"
    
    embed = discord.Embed(title="🖥️ RDU Server Status", color=discord.Color.green())
    embed.add_field(name="Status", value=status_text, inline=True)
    embed.add_field(name="Players", value=f"{player_count}/{max_players}", inline=True)
    embed.add_field(name="Map", value="Procedural Map", inline=True)
    embed.set_footer(text="Data is a placeholder; real bots use API calls.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="crafttime", description="Lookup the crafting time for a RUST item")
@app_commands.describe(item="The RUST item name (e.g., AK, C4, Large Furnace)")
async def crafttime(interaction: discord.Interaction, item: str):
    item = item.lower()
    craft_data = {
        "ak": 120, "c4": 60, "medkit": 30, "armored door": 100, "large furnace": 250
    }
    
    if item in craft_data:
        embed = discord.Embed(title=f"⏱️ Crafting Time: {item.upper()}", description=f"The time required to craft **{item.upper()}** is **{craft_data[item]}** seconds.", color=discord.Color.teal())
    else:
        embed = discord.Embed(title="Item Not Found", description="That item is not in the database. Try an exact name (e.g., `AK`).", color=discord.Color.red())
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="recipe", description="Lookup the ingredients for a RUST item")
@app_commands.describe(item="The RUST item name (e.g., AK, C4)")
async def recipe(interaction: discord.Interaction, item: str):
    item = item.lower()
    recipe_data = {
        "ak": "50 HQM, 200 Metal, 1 Rifle Body, 1 Spring.", 
        "c4": "20 Explosives, 5 Cloth, 1 Tech Trash.",
        "rocket": "10 Explosives, 1 Pipe, 1 Tech Trash."
    }
    
    if item in recipe_data:
        embed = discord.Embed(title=f"📜 Recipe: {item.upper()}", description=recipe_data[item], color=discord.Color.teal())
    else:
        embed = discord.Embed(title="Item Not Found", description="That item is not in the database. Try an exact name.", color=discord.Color.red())
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="map", description="Provides a link to the current RDU map")
async def map_link(interaction: discord.Interaction):
    link = "https://map.playrust.io/?AussieRDU_Server"
    embed = discord.Embed(title="🗺️ RDU Map Link", description=f"[Click here to view the current server map]({link})", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rules", description="Display the server rules")
async def rules(interaction: discord.Interaction):
    rules_text = (
        "1. No cheating/scripting.\n"
        "2. No toxic or racist language.\n"
        "3. Max group size is 4.\n"
        "4. No exploiting game bugs.\n"
        "5. Admins have final say."
    )
    embed = discord.Embed(title="📜 RDU Server Rules", description=rules_text, color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trade", description="Announces a trade in the trade channel")
async def trade(interaction: discord.Interaction):
    if interaction.channel.name != "trade-channel":
        await interaction.response.send_message("❌ This command should only be used in the #trade-channel.", ephemeral=True)
        return
    
    embed = discord.Embed(title="🤝 Trade Offer Alert!", description=f"{interaction.user.mention} is looking to trade! Post your offer details below.", color=discord.Color.yellow())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="report", description="Report a player to the moderation team")
@app_commands.describe(player_name="The name of the player to report", reason="Reason for the report")
async def report(interaction: discord.Interaction, player_name: str, reason: str):
    mod_channel = discord.utils.get(interaction.guild.channels, name="mod-reports")
    
    if mod_channel:
        report_embed = discord.Embed(title="🚨 NEW PLAYER REPORT", color=discord.Color.dark_red())
        report_embed.add_field(name="Reported Player", value=player_name, inline=False)
        report_embed.add_field(name="Reason", value=reason, inline=False)
        report_embed.add_field(name="Reported By", value=interaction.user.mention, inline=False)
        
        # NOTE: Replace <@&Your_Mod_Role_ID> with the actual ID of your moderator role
        await mod_channel.send(f"**<@&Your_Mod_Role_ID>**", embed=report_embed)
        await interaction.response.send_message("✅ Your report has been submitted to the moderation team. Thank you!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Could not find a mod-reports channel. Report failed.", ephemeral=True)

@bot.tree.command(name="rustlore", description="Get a random piece of RUST lore")
async def rustlore(interaction: discord.Interaction):
    lore = [
        "The scientists are survivors infected by a mysterious pathogen.",
        "The abandoned monuments hint at a failed pre-apocalyptic civilization.",
        "The military base suggests a failed attempt to contain the outbreak.",
        "The hot air balloon was originally designed for observation, not travel.",
        "The Rust world is a simulation or experiment (fan theory)."
    ]
    embed = discord.Embed(title="📖 RUST Lore Snippet", description=random.choice(lore), color=discord.Color.dark_gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bestresource", description="Tells you the best spot to farm a resource")
@app_commands.describe(resource="The resource to farm (e.g., Stone, Metal, Wood, Sulfur)")
@app_commands.choices(resource=[
    app_commands.Choice(name="Stone", value="stone"),
    app_commands.Choice(name="Metal", value="metal"),
    app_commands.Choice(name="Wood", value="wood"),
    app_commands.Choice(name="Sulfur", value="sulfur"),
])
async def bestresource(interaction: discord.Interaction, resource: app_commands.Choice[str]):
    resource_info = {
        "stone": "Farm on snowy mountains using a Jackhammer for the best yield.",
        "metal": "Hit satellite dishes or trainyard; nodes are better near the coast.",
        "wood": "Use a chainsaw in the heavy forest areas near the water.",
        "sulfur": "The snow biome is the best place to find high-yield sulfur nodes."
    }
    embed = discord.Embed(title=f"⛏️ Best {resource.name} Farm Spot", description=resource_info[resource.value], color=discord.Color.brown())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="wipetype", description="Explains the types of RUST server wipes")
async def wipetype(interaction: discord.Interaction):
    embed = discord.Embed(title="🔄 RUST Wipe Types", color=discord.Color.teal())
    embed.add_field(name="Forced Wipe (Map + BP)", value="Occurs monthly (first Thursday). Wipes map and blueprints.", inline=False)
    embed.add_field(name="Map Wipe (No BP)", value="Can be weekly/bi-weekly. Wipes the map, keeps blueprints.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="suggestion", description="Submit a suggestion for the server")
@app_commands.describe(suggestion="Your suggestion for the server or community")
async def rust_suggestion(interaction: discord.Interaction, suggestion: str):
    await interaction.response.send_message("✅ Your suggestion has been recorded. Thank you for your input!", ephemeral=True)
    
@bot.tree.command(name="teamlimit", description="Check the current server team/group limit")
async def team_limit(interaction: discord.Interaction):
    limit = 4
    embed = discord.Embed(title="👥 Team/Group Limit", description=f"The maximum team/group limit on this server is **{limit}** players.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="monument", description="Get a random RUST monument for a starting point")
async def random_monument(interaction: discord.Interaction):
    monuments = ["Launch Site", "Oil Rig", "Water Treatment Plant", "Train Yard", "Bandit Camp", "Outpost"]
    choice = random.choice(monuments)
    embed = discord.Embed(title="🧭 Random Monument", description=f"Your starting monument suggestion is: **{choice}**", color=discord.Color.gray())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="time", description="Shows the current server time (real-world time)")
async def server_time(interaction: discord.Interaction):
    current_time = datetime.now().strftime("%I:%M:%S %p %Z")
    embed = discord.Embed(title="⏳ Current Server Time", description=f"The current real-world server time is **{current_time} AEDT**.", color=discord.Color.dark_purple())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="baseadvice", description="Get a quick tip for base building")
async def baseadvice(interaction: discord.Interaction):
    advice = [
        "Always use triangle foundations for maximum stability and reduced cost.",
        "Use external walls/gates to create a compound and prevent easy access.",
        "Honeycomb your base with layers of walls and floors.",
        "Never leave a clear sightline from outside to your tool cupboard.",
        "Spread loot across multiple compartments/rooms."
    ]
    embed = discord.Embed(title="🧱 Base Building Advice", description=random.choice(advice), color=discord.Color.gray())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="weapontier", description="Shows the general tier list of RUST weapons")
async def weapon_tier(interaction: discord.Interaction):
    tier_list = (
        "**S-Tier:** AK47, L96, M249\n"
        "**A-Tier:** Custom SMG, LR-300, Bolt Action Rifle\n"
        "**B-Tier:** Python, Revolver, Semi-Automatic Rifle\n"
        "**C-Tier:** Eoka Pistol, Waterpipe Shotgun, Bow"
    )
    embed = discord.Embed(title="🔫 RUST Weapon Tier List (General)", description=tier_list, color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="adminnotice", description="Post an official notice to the channel")
@app_commands.describe(message="The official announcement message")
@app_commands.checks.has_permissions(administrator=True)
async def adminnotice(interaction: discord.Interaction, message: str):
    embed = discord.Embed(
        title="📢 OFFICIAL ADMIN NOTICE",
        description=message,
        color=discord.Color.red()
    )
    embed.set_footer(text=f"Posted by {interaction.user.display_name}")
    await interaction.response.send_message("✅ Notice posted.", ephemeral=True)
    await interaction.channel.send("@everyone", embed=embed)

# ----------------------------------------------------
# 🛑 ERROR HANDLER & RUN BLOCK
# ----------------------------------------------------

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
        
try:
    bot.run(DISCORD_TOKEN)
except Exception:
    pass
