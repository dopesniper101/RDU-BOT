# Installation commands
!pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib discord

import os
import sys
import logging
from datetime import datetime
import asyncio
import random
from typing import Optional

# Imports for Google Drive API
import pickle
import mimetypes
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import csv

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

# --- GOOGLE DRIVE UPLOAD FUNCTIONS ---
# SCOPES needed for Drive access
SCOPES = ['https://www.googleapis.com/auth/drive.file'] 

def get_gdrive_service():
    """Authenticates and returns the Google Drive API service object."""
    creds = None
    TOKEN_FILE = 'token.pickle'
    CREDS_FILE = 'credentials.json'

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_FILE):
                print(f"ERROR: Missing {CREDS_FILE}. Follow the Google Drive setup steps.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f"An authentication error occurred: {error}")
        return None

def upload_to_drive(file_path: str, folder_id: Optional[str] = None) -> Optional[str]:
    """
    Uploads a file to Google Drive.
    
    Args:
        file_path: The path to the local file to upload.
        folder_id: The optional ID of the folder to upload the file to.
                   If None, uploads to the root folder.
    
    Returns:
        The ID of the uploaded file, or None if the upload failed.
    """
    if not os.path.exists(file_path):
        print(f"ERROR: Local file not found at {file_path}")
        return None
        
    try:
        service = get_gdrive_service()
        if not service:
            return None

        mimetype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

        file_metadata = {
            'name': os.path.basename(file_path),
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        
        # Check if file already exists with the same name and in the same folder
        # This is a simple check; for real apps, consider searching by name and parent ID.
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        print(f"Successfully uploaded {file_path}. File ID: {file.get('id')}")
        return file.get('id')

    except HttpError as error:
        print(f"An API error occurred during upload: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# --- RDU_BOT CLASS ---
class RDU_BOT(commands.Bot):
    def __init__(self):
        # Setting the initial bot configuration
        intents = discord.Intents.default()
        intents.message_content = True # Required to read message content for auto-responses
        intents.members = True # Required for logging new/removed members
        super().__init__(command_prefix=commands.when_mentioned_or("!"), description=DESCRIPTION, intents=intents, owner_id=ADMIN_ID)
        self.log_channel_id = None
        self.detection_settings = {} # {guild_id: {'keyword': 'response'}}

    async def _log_action(self, title: str, description: str, moderator: discord.Member, color: discord.Color):
        """Sends a standardized log message to the dedicated log channel."""
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title=title,
                    description=description,
                    color=color,
                    timestamp=datetime.now()
                )
                log_embed.set_footer(text=f"Action by: {moderator.name}#{moderator.discriminator}", icon_url=moderator.avatar.url if moderator.avatar else discord.Embed.Empty)
                await log_channel.send(embed=log_embed)
            else:
                logger.warning(f"Log channel with ID {self.log_channel_id} not found.")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("-" * 20)

        # Attempt to set up the log channel ID
        for guild in self.guilds:
            log_channel = utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
            if log_channel:
                self.log_channel_id = log_channel.id
                logger.info(f"Found log channel in '{guild.name}' with ID: {self.log_channel_id}")
                break
        
        # Sync application commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} application commands globally.")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_message(self, message):
        if message.author.bot:
            return

        guild_id = message.guild.id if message.guild else None
        if guild_id and guild_id in self.detection_settings:
            settings = self.detection_settings[guild_id]
            keyword = settings['keyword']
            response = settings['response']

            if keyword in message.content.lower():
                await message.channel.send(response, delete_after=30)
                
                # Log the auto-response action
                await self._log_action(
                    title="🤖 Auto-Response Triggered",
                    description=f"Keyword `{keyword}` matched.\n**User:** {message.author.mention}\n**Channel:** {message.channel.mention}",
                    moderator=self.user,
                    color=discord.Color.gold()
                )

        await self.process_commands(message)

    @app_commands.command(name="ping", description="Checks the bot's latency.")
    async def ping_command(self, interaction: discord.Interaction):
        latency = round(self.latency * 1000)
        embed = create_embed(
            title="🏓 Pong!",
            description=f"My latency is **{latency}ms**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_autoresponse", description="Set a keyword and a text response for the server.")
    @app_commands.describe(keyword="The word that will trigger the response.", response="The message the bot will send.")
    @is_owner()
    async def set_autoresponse_command(self, interaction: discord.Interaction, keyword: str, response: str):
        guild_id = interaction.guild_id
        self.detection_settings[guild_id] = {'keyword': keyword.lower(), 'response': response}

        # Log the action
        await self._log_action(
            title="✏️ Auto-Response SET",
            description=f"New auto-response set.\n**Keyword:** `{keyword.lower()}`\n**Response:** `{response[:100]}...`",
            moderator=interaction.user,
            color=discord.Color.blue()
        )

        embed = create_embed(
            title="✅ Auto-Response Set",
            description=f"A new auto-response has been set for the keyword `{keyword.lower()}`.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reset_autoresponse", description="Removes the keyword auto-response for the server.")
    @is_owner()
    async def reset_autoresponse_command(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in self.detection_settings:
            del self.detection_settings[guild_id]

            # Log the action
            await self._log_action(
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

    @app_commands.command(name="backup_logs", description="Generates and uploads a usage report to Google Drive.")
    @is_owner()
    async def backup_logs_command(self, interaction: discord.Interaction):
        # 1. Create a dynamic, timestamped file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"bot_usage_report_{timestamp}.csv"
        
        # Simulate generating a report file on the local file system
        try:
            with open(file_name, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Guild ID", "Bot Name"])
                for guild in self.guilds:
                    writer.writerow([datetime.now().isoformat(), guild.id, BOT_NAME])
        except Exception as e:
             await interaction.response.send_message(f"❌ Failed to create local file: {e}", ephemeral=True)
             return
        
        # 2. Upload the file to Google Drive
        # NOTE: You must have 'credentials.json' set up for this to work.
        uploaded_id = upload_to_drive(file_name, folder_id=None) # Replace None with a specific folder ID string to upload to a subfolder

        # 3. Respond to the user and log the action
        if uploaded_id:
            message = f"✅ Usage report uploaded to Google Drive. File ID: `{uploaded_id}`"
            color = discord.Color.green()
            # Clean up the local file after upload
            try:
                os.remove(file_name)
            except OSError as e:
                logger.error(f"Error removing local file {file_name}: {e}")
                
        else:
            message = "❌ **Upload Failed.** Check 'credentials.json' and local log/token files for setup errors."
            color = discord.Color.red()

        # Log the action
        await self._log_action(
            title="💾 Google Drive Backup",
            description=message,
            moderator=interaction.user,
            color=color
        )

        embed = discord.Embed(
            title="Drive Backup Status",
            description=message,
            color=color
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
