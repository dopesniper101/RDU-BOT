# Installation commands
import os
os.system("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib discord")

import sys
import logging
import pickle
import mimetypes
import asyncio
import random
import csv
from datetime import datetime
from typing import Optional

# Google API Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Discord Imports
import discord
from discord.ext import commands
from discord import app_commands, utils
from discord.ext.commands import is_owner

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('TOKEN')
BOT_NAME = "RUST DOWN UNDER"
DESCRIPTION = "A Discord bot for the RUST DOWN UNDER community"
LOG_CHANNEL_NAME = "bot-logs"
ADMIN_ID = 123456789012345678  # Replace with your actual ID

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- UTILITY FUNCTIONS ---
def create_embed(title: str, description: str, color: discord.Color = discord.Color.blue(), footer: str = "Auto-deleting in 30 seconds.") -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
    embed.set_footer(text=footer)
    return embed

# --- GOOGLE DRIVE INTEGRATION ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_gdrive_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                logger.error("Missing credentials.json for Google Drive.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    try:
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Gdrive Auth Error: {e}")
        return None

def upload_to_drive(file_path: str, folder_id: Optional[str] = None) -> Optional[str]:
    if not os.path.exists(file_path): return None
    try:
        service = get_gdrive_service()
        if not service: return None
        mimetype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        file_metadata = {'name': os.path.basename(file_path)}
        if folder_id: file_metadata['parents'] = [folder_id]
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Drive Upload Error: {e}")
        return None

# --- BOT CLASS ---
class RDU_BOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", description=DESCRIPTION, intents=intents, owner_id=ADMIN_ID)
        self.detection_settings = {}

    async def _log_to_channel(self, embed: discord.Embed):
        """Internal helper to find the log channel and send the embed."""
        for guild in self.guilds:
            channel = utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
            if channel:
                await channel.send(embed=embed)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} commands.")
        except Exception as e:
            logger.error(f"Sync failed: {e}")

    # --- ENHANCED LOGGING EVENTS ---
    async def on_member_join(self, member):
        embed = create_embed("📥 Member Joined", f"{member.mention} joined the server.", discord.Color.green(), f"ID: {member.id}")
        await self._log_to_channel(embed)

    async def on_member_remove(self, member):
        embed = create_embed("📤 Member Left", f"**{member.name}** has left the server.", discord.Color.red(), f"ID: {member.id}")
        await self._log_to_channel(embed)

    async def on_message_delete(self, message):
        if message.author.bot: return
        embed = create_embed("🗑️ Message Deleted", f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Content:** {message.content}", discord.Color.orange(), "Log Audit")
        await self._log_to_channel(embed)

    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        embed = create_embed("✏️ Message Edited", f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}\n**Before:** {before.content}\n**After:** {after.content}", discord.Color.blue(), "Log Audit")
        await self._log_to_channel(embed)

    async def on_message(self, message):
        if message.author.bot: return
        
        # Auto-response Logic
        guild_id = message.guild.id if message.guild else None
        if guild_id and guild_id in self.detection_settings:
            sets = self.detection_settings[guild_id]
            if sets['keyword'] in message.content.lower():
                resp_embed = create_embed("🤖 Auto-Response", sets['response'], discord.Color.gold())
                await message.channel.send(embed=resp_embed, delete_after=30)
                
                log_embed = create_embed("🎯 Trigger Hit", f"Keyword `{sets['keyword']}` used by {message.author.mention}", discord.Color.light_grey(), "Automation")
                await self._log_to_channel(log_embed)

        await self.process_commands(message)

    # --- COMMANDS ---
    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.latency * 1000)
        await interaction.response.send_message(embed=create_embed("🏓 Pong!", f"Latency: {latency}ms", discord.Color.green()), ephemeral=True)

    @app_commands.command(name="set_autoresponse", description="Set a trigger keyword")
    @is_owner()
    async def set_auto(self, interaction: discord.Interaction, keyword: str, response: str):
        self.detection_settings[interaction.guild_id] = {'keyword': keyword.lower(), 'response': response}
        embed = create_embed("✅ Set Success", f"Trigger: `{keyword}`", discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._log_to_channel(create_embed("⚙️ Config Updated", f"Auto-response set by {interaction.user.mention}", discord.Color.blue()))

    @app_commands.command(name="backup_logs", description="Upload server stats to Google Drive")
    @is_owner()
    async def backup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"rdu_log_{ts}.csv"
        
        try:
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Guild", "Members"])
                for g in self.guilds:
                    writer.writerow([ts, g.name, g.member_count])
            
            drive_id = upload_to_drive(fname)
            if drive_id:
                msg = f"Backup Successful! Drive ID: `{drive_id}`"
                color = discord.Color.green()
                os.remove(fname)
            else:
                msg = "Upload failed. Check Colab logs for credentials error."
                color = discord.Color.red()
            
            emb = create_embed("💾 Drive Backup", msg, color)
            await interaction.followup.send(embed=emb)
            await self._log_to_channel(emb)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot = RDU_BOT()
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: No Token found.")
