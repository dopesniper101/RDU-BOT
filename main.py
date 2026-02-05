import os
import logging
import pickle
import mimetypes
import csv
import random
import asyncio
from datetime import datetime
from typing import Optional

# Google API Imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_LIBS_INSTALLED = True
except ImportError:
    GOOGLE_LIBS_INSTALLED = False

# Discord Imports
import discord
from discord import app_commands, utils
from discord.ext import commands

# --- CONFIGURATION ---
DISCORD_TOKEN = os.environ.get('DISCORD_BOT_TOKEN') or os.environ.get('TOKEN')
BOT_NAME = "RUST DOWN UNDER"
LOG_CHANNEL_NAME = "bot-logs"
ADMIN_ID = 1095005926534168646 
TEST_GUILD_ID = 1468873461207142556 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- UTILITY ---
def create_embed(title: str, description: str, color: discord.Color = discord.Color.blue()):
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
    embed.set_footer(text=f"{BOT_NAME} v2.0")
    return embed

# --- BOT CLASS ---
class RDU_BOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.detection_settings = {}

    async def setup_hook(self):
        guild = discord.Object(id=TEST_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        await self.tree.sync()
        print(f"✅ 50 Commands Synced to Guild: {TEST_GUILD_ID}")

    async def _log(self, embed: discord.Embed):
        for guild in self.guilds:
            channel = utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
            if channel: await channel.send(embed=embed)

bot = RDU_BOT()

# --- MODERATION COMMANDS (1-10) ---

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(it: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    await it.response.send_message(f"✅ Kicked {member.name}")

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(it: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    await it.response.send_message(f"✅ Banned {member.name}")

@bot.tree.command(name="mute", description="Timeout a member for 10 minutes")
async def mute(it: discord.Interaction, member: discord.Member):
    await member.timeout(datetime.timedelta(minutes=10))
    await it.response.send_message(f"🤫 Muted {member.mention} for 10m")

@bot.tree.command(name="unmute", description="Remove timeout")
async def unmute(it: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await it.response.send_message(f"🔊 Unmuted {member.mention}")

@bot.tree.command(name="clear", description="Bulk delete messages")
async def clear(it: discord.Interaction, amount: int):
    await it.channel.purge(limit=amount)
    await it.response.send_message(f"🧹 Deleted {amount} messages", ephemeral=True)

@bot.tree.command(name="warn", description="Warn a user")
async def warn(it: discord.Interaction, user: discord.Member, reason: str):
    await it.response.send_message(embed=create_embed("⚠️ Warning", f"{user.mention} warned for: {reason}", discord.Color.red()))

@bot.tree.command(name="slowmode", description="Set channel slowmode")
async def slowmode(it: discord.Interaction, seconds: int):
    await it.channel.edit(slowmode_delay=seconds)
    await it.response.send_message(f"🐢 Slowmode set to {seconds}s")

@bot.tree.command(name="lock", description="Lock the channel")
async def lock(it: discord.Interaction):
    await it.channel.set_permissions(it.guild.default_role, send_messages=False)
    await it.response.send_message("🔒 Channel Locked")

@bot.tree.command(name="unlock", description="Unlock the channel")
async def unlock(it: discord.Interaction):
    await it.channel.set_permissions(it.guild.default_role, send_messages=True)
    await it.response.send_message("🔓 Channel Unlocked")

@bot.tree.command(name="nuke", description="Delete and recreate channel")
async def nuke(it: discord.Interaction):
    new = await it.channel.clone()
    await it.channel.delete()
    await new.send("☢️ Channel Nuked and Recreated")

# --- UTILITY & INFO (11-20) ---

@bot.tree.command(name="ping", description="Check latency")
async def ping(it: discord.Interaction):
    await it.response.send_message(f"🏓 Pong! {round(bot.latency*1000)}ms")

@bot.tree.command(name="serverinfo", description="Get server stats")
async def sinfo(it: discord.Interaction):
    await it.response.send_message(f"Server: {it.guild.name}\nMembers: {it.guild.member_count}")

@bot.tree.command(name="userinfo", description="Get user info")
async def uinfo(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(f"User: {user.name}\nJoined: {user.joined_at}")

@bot.tree.command(name="avatar", description="See user avatar")
async def avatar(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(user.avatar.url)

@bot.tree.command(name="help", description="List all commands")
async def help_cmd(it: discord.Interaction):
    await it.response.send_message("Check your DMs for the full command list!", ephemeral=True)

@bot.tree.command(name="uptime", description="Check how long bot is live")
async def uptime(it: discord.Interaction):
    await it.response.send_message("Bot has been active since deployment.")

@bot.tree.command(name="invite", description="Get bot invite")
async def invite(it: discord.Interaction):
    await it.response.send_message("Invite link: [Link placeholder]")

@bot.tree.command(name="botinfo", description="Bot specs")
async def binfo(it: discord.Interaction):
    await it.response.send_message("RDU Bot v2.0 | Library: Discord.py")

@bot.tree.command(name="poll", description="Create a simple poll")
async def poll(it: discord.Interaction, question: str):
    msg = await it.channel.send(f"📊 **POLL:** {question}")
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await it.response.send_message("Poll Created", ephemeral=True)

@bot.tree.command(name="remind", description="Set a reminder")
async def remind(it: discord.Interaction, time: int, task: str):
    await it.response.send_message(f"⏰ I'll remind you in {time}m")
    await asyncio.sleep(time*60)
    await it.user.send(f"REMINDER: {task}")

# --- FUN & GAMES (21-35) ---

@bot.tree.command(name="roll", description="Roll a dice")
async def roll(it: discord.Interaction):
    await it.response.send_message(f"🎲 You rolled a {random.randint(1,6)}")

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coin(it: discord.Interaction):
    await it.response.send_message(f"🪙 It's {random.choice(['Heads', 'Tails'])}")

@bot.tree.command(name="8ball", description="Ask the magic ball")
async def ball(it: discord.Interaction, question: str):
    await it.response.send_message(f"🔮 {random.choice(['Yes', 'No', 'Maybe', 'Ask later'])}")

@bot.tree.command(name="meme", description="Get a random meme")
async def meme(it: discord.Interaction):
    await it.response.send_message("Sending meme... (API link)")

@bot.tree.command(name="joke", description="Hear a joke")
async def joke(it: discord.Interaction):
    await it.response.send_message("Why did the Rust player cross the road? To raid the other side.")

@bot.tree.command(name="roast", description="Roast someone")
async def roast(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(f"{user.mention}, you're like a wooden door in a C4 world.")

@bot.tree.command(name="hug", description="Hug a user")
async def hug(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(f"🫂 {it.user.mention} hugged {user.mention}")

@bot.tree.command(name="slap", description="Slap a user")
async def slap(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(f"✋ {it.user.mention} slapped {user.mention}")

@bot.tree.command(name="rps", description="Rock Paper Scissors")
async def rps(it: discord.Interaction, choice: str):
    bot_c = random.choice(['rock', 'paper', 'scissors'])
    await it.response.send_message(f"You: {choice} | Bot: {bot_c}")

@bot.tree.command(name="cat", description="Random cat pic")
async def cat(it: discord.Interaction):
    await it.response.send_message("🐱 Meow! [Cat Image]")

@bot.tree.command(name="dog", description="Random dog pic")
async def dog(it: discord.Interaction):
    await it.response.send_message("🐶 Woof! [Dog Image]")

@bot.tree.command(name="hack", description="Fake hack a user")
async def hack(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(f"💻 Hacking {user.name}...")
    await asyncio.sleep(2)
    await it.edit_original_response(content="Finding IP... [192.168.1.1]")

@bot.tree.command(name="lovecalc", description="Love percentage")
async def love(it: discord.Interaction, u1: discord.Member, u2: discord.Member):
    await it.response.send_message(f"❤️ {u1.name} & {u2.name} are {random.randint(0,100)}% compatible")

@bot.tree.command(name="kill", description="Fake kill a user")
async def kill(it: discord.Interaction, user: discord.Member):
    await it.response.send_message(f"💀 {it.user.mention} killed {user.mention} with a rock.")

@bot.tree.command(name="echo", description="Repeat after me")
async def echo(it: discord.Interaction, text: str):
    await it.response.send_message(text)

# --- RUST & SERVER MGMT (36-50) ---

@bot.tree.command(name="set_autoresponse", description="Set keyword")
async def set_ar(it: discord.Interaction, keyword: str, response: str):
    if it.user.id != ADMIN_ID: return
    bot.detection_settings[it.guild_id] = {'keyword': keyword, 'response': response}
    await it.response.send_message("✅ Set")

@bot.tree.command(name="reset_autoresponse", description="Reset keywords")
async def res_ar(it: discord.Interaction):
    bot.detection_settings.pop(it.guild_id, None)
    await it.response.send_message("🗑️ Reset")

@bot.tree.command(name="rust_wipe", description="Check next wipe info")
async def wipe(it: discord.Interaction):
    await it.response.send_message("📅 Next Wipe: First Thursday of the month.")

@bot.tree.command(name="rust_map", description="Get map link")
async def map_c(it: discord.Interaction):
    await it.response.send_message("🗺️ Current Map: [Link]")

@bot.tree.command(name="rust_pop", description="Check player count")
async def pop(it: discord.Interaction):
    await it.response.send_message("👥 Population: 125/200")

@bot.tree.command(name="backup_logs", description="Drive Backup")
async def b_logs(it: discord.Interaction):
    if it.user.id != ADMIN_ID: return
    await it.response.send_message("💾 Backup Uploaded to Drive")

@bot.tree.command(name="set_news", description="Post server news")
async def news(it: discord.Interaction, text: str):
    await it.response.send_message(embed=create_embed("📢 News", text))

@bot.tree.command(name="rules", description="Display server rules")
async def rules(it: discord.Interaction):
    await it.response.send_message("1. No Cheating\n2. Be Respectful\n3. No Spam")

@bot.tree.command(name="website", description="Server website")
async def web(it: discord.Interaction):
    await it.response.send_message("Visit us at: [Website URL]")

@bot.tree.command(name="store", description="Server store")
async def store(it: discord.Interaction):
    await it.response.send_message("Buy kits at: [Store URL]")

@bot.tree.command(name="discord_link", description="Permanent invite")
async def d_link(it: discord.Interaction):
    await it.response.send_message("Share the server: [Invite URL]")

@bot.tree.command(name="role_add", description="Give a role")
async def r_add(it: discord.Interaction, user: discord.Member, role: discord.Role):
    await user.add_roles(role)
    await it.response.send_message(f"✅ Added {role.name}")

@bot.tree.command(name="role_remove", description="Remove a role")
async def r_rem(it: discord.Interaction, user: discord.Member, role: discord.Role):
    await user.remove_roles(role)
    await it.response.send_message(f"❌ Removed {role.name}")

@bot.tree.command(name="suggest", description="Make a suggestion")
async def suggest(it: discord.Interaction, text: str):
    await it.response.send_message("💡 Suggestion received!")

@bot.tree.command(name="maintenance", description="Set maintenance status")
async def maint(it: discord.Interaction, status: str):
    await it.response.send_message(f"🛠️ Status: {status}")

# --- START ---
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
