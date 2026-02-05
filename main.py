import os
import logging
import pickle
import mimetypes
import csv
from datetime import datetime
from typing import Optional

# Google API Imports (Fail-safe for Railway)
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
ADMIN_ID = 123456789012345678 # Replace with your Discord User ID
# ⚠️ REPLACE THIS WITH YOUR SERVER (GUILD) ID FOR INSTANT COMMAND SYNC
TEST_GUILD_ID = 123456789012345678 

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- UTILITY ---
def create_embed(title: str, description: str, color: discord.Color = discord.Color.blue(), footer: str = "RDU System"):
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
    embed.set_footer(text=footer)
    return embed

# --- GOOGLE DRIVE LOGIC ---
def get_gdrive_service():
    if not GOOGLE_LIBS_INSTALLED: return None
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token: creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: creds.refresh(Request())
            except: return None
        else: return None 
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path: str):
    service = get_gdrive_service()
    if not service: return None
    try:
        media = MediaFileUpload(file_path, mimetype='text/csv', resumable=True)
        file = service.files().create(body={'name': os.path.basename(file_path)}, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return None

# --- BOT CLASS ---
class RDU_BOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.detection_settings = {}

    async def setup_hook(self):
        """Syncs slash commands instantly to your specific server."""
        guild = discord.Object(id=TEST_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        # Also sync globally (takes up to 1 hour for other servers)
        await self.tree.sync()
        print(f"✅ Slash commands synced to guild {TEST_GUILD_ID}")

    async def _log_to_channel(self, embed: discord.Embed):
        for guild in self.guilds:
            channel = utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
            if channel: await channel.send(embed=embed)

    async def on_ready(self):
        print(f"✅ {BOT_NAME} is Online | User: {self.user}")

    # --- LOGGING EVENTS ---
    async def on_member_join(self, member):
        await self._log_to_channel(create_embed("📥 Member Joined", f"{member.mention} has arrived.", discord.Color.green()))

    async def on_member_remove(self, member):
        await self._log_to_channel(create_embed("📤 Member Left", f"**{member.name}** has departed.", discord.Color.red()))

    async def on_message_delete(self, message):
        if message.author.bot: return
        await self._log_to_channel(create_embed("🗑️ Message Deleted", f"**Author:** {message.author.mention}\n**Text:** {message.content}", discord.Color.orange()))

    async def on_message(self, message):
        if message.author.bot: return
        gid = message.guild.id if message.guild else None
        if gid and gid in self.detection_settings:
            sets = self.detection_settings[gid]
            if sets['keyword'] in message.content.lower():
                # Embedded auto-response
                await message.channel.send(embed=create_embed("🤖 System Response", sets['response'], discord.Color.gold()), delete_after=30)
        await self.process_commands(message)

# --- INSTANCE ---
bot = RDU_BOT()

# --- SLASH COMMANDS ---

@bot.tree.command(name="help", description="Show all available RDU commands")
async def help_cmd(interaction: discord.Interaction):
    embed = create_embed("📖 RDU Help Menu", "Use the following slash commands:")
    embed.add_field(name="/ping", value="Check latency.", inline=True)
    embed.add_field(name="/set_autoresponse", value="Set trigger word.", inline=False)
    embed.add_field(name="/reset_autoresponse", value="Clear trigger word.", inline=False)
    embed.add_field(name="/backup_logs", value="Export stats to Drive.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Check the bot's heartbeat")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(embed=create_embed("🏓 Pong!", f"Latency: **{latency}ms**", discord.Color.green()), ephemeral=True)

@bot.tree.command(name="set_autoresponse", description="Set a trigger keyword (Admin Only)")
@app_commands.describe(keyword="Word to trigger", response="What the bot says")
async def set_auto(interaction: discord.Interaction, keyword: str, response: str):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
    
    bot.detection_settings[interaction.guild_id] = {'keyword': keyword.lower(), 'response': response}
    await interaction.response.send_message(embed=create_embed("✅ Auto-Response Set", f"**Trigger:** `{keyword}`", discord.Color.green()), ephemeral=True)
    await bot._log_to_channel(create_embed("⚙️ Settings Update", f"Auto-response set by {interaction.user.mention}", discord.Color.blue()))

@bot.tree.command(name="reset_autoresponse", description="Remove the trigger keyword (Admin Only)")
async def reset_auto(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
    
    bot.detection_settings.pop(interaction.guild_id, None)
    await interaction.response.send_message(embed=create_embed("🗑️ Reset Complete", "Auto-response cleared.", discord.Color.red()), ephemeral=True)

@bot.tree.command(name="backup_logs", description="Upload server statistics to Google Drive (Admin Only)")
async def backup(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
    
    # We "defer" because Drive upload might take longer than 3 seconds
    await interaction.response.defer(ephemeral=True)
    
    ts = datetime.now().strftime("%Y-%m-%d")
    fname = f"rdu_stats_{ts}.csv"
    
    try:
        with open(fname, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Guild Name", "Total Members", "Timestamp"])
            for g in bot.guilds:
                writer.writerow([g.name, g.member_count, datetime.now().isoformat()])
        
        drive_id = upload_to_drive(fname)
        if drive_id:
            os.remove(fname)
            await interaction.followup.send(embed=create_embed("💾 Drive Backup", f"Success! File ID: `{drive_id}`", discord.Color.green()))
        else:
            await interaction.followup.send("❌ Drive Error: Could not authenticate or upload.")
    except Exception as e:
        await interaction.followup.send(f"❌ Critical Error: {str(e)}")

# --- START ---
if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("FATAL ERROR: DISCORD_BOT_TOKEN not found in environment.")
