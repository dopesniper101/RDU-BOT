import os
import logging
import discord
import asyncio
from datetime import datetime
from typing import Final, Optional, List
from discord import app_commands
from discord.ext import commands

# --- CONFIGURATION ---
class Config:
    TOKEN: Final = os.environ.get('DISCORD_TOKEN')
    # Default to 0 if not provided to avoid int() conversion errors
    GUILD_ID: Final = int(os.environ.get('GUILD_ID', 0)) 
    LOG_CHANNEL_NAME: Final = "bot-logs"
    VERSION: Final = "v2.2.0"
    BOT_NAME: Final = "RUST DOWN UNDER"
    COLOR_SUCCESS: Final = discord.Color.green()
    COLOR_ERROR: Final = discord.Color.red()
    COLOR_INFO: Final = discord.Color.blue()
    COLOR_WARNING: Final = discord.Color.gold()

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(name)s: %(message)s'
)
logger = logging.getLogger("RDU_SYSTEM")

# --- UI UTILS ---
class EmbedFactory:
    """Centralized factory to ensure consistent branding across all commands."""
    @staticmethod
    def create(
        title: str, 
        description: str, 
        color: discord.Color = Config.COLOR_INFO,
        footer_ext: Optional[str] = None
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title, 
            description=description, 
            color=color, 
            timestamp=datetime.utcnow()
        )
        footer_text = f"{Config.BOT_NAME} {Config.VERSION}"
        if footer_ext:
            footer_text += f" | {footer_ext}"
        embed.set_footer(text=footer_text)
        return embed

# --- MODERATION COG ---
class Moderation(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="ban", description="Permanently ban a member and purge messages")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The target user", reason="Reason for the ban")
    async def ban(self, it: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= it.user.top_role:
            return await it.response.send_message("❌ Cannot action user with higher/equal role.", ephemeral=True)
        
        await member.ban(reason=f"Mod: {it.user.name} | {reason}")
        embed = EmbedFactory.create("🔨 Member Banned", f"**Target:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {it.user.mention}", Config.COLOR_ERROR)
        await it.response.send_message(embed=embed)
        await self.bot.log_action(it.guild, embed)

    @app_commands.command(name="clear", description="Bulk delete messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(amount="Amount of messages to remove (1-100)")
    async def clear(self, it: discord.Interaction, amount: int):
        if not 1 <= amount <= 100:
            return await it.response.send_message("❌ Please provide a number between 1 and 100.", ephemeral=True)
            
        await it.response.defer(ephemeral=True)
        deleted = await it.channel.purge(limit=amount)
        await it.edit_original_response(content=f"🧹 Purged {len(deleted)} messages.")

    @app_commands.command(name="slowmode", description="Adjust channel ratelimit")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, it: discord.Interaction, seconds: int):
        await it.channel.edit(slowmode_delay=seconds)
        await it.response.send_message(f"🐢 Slowmode updated to {seconds}s.", ephemeral=True)

# --- INFORMATION COG ---
class Information(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="server_status", description="Real-time Rust & Discord metrics")
    async def server_status(self, it: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = EmbedFactory.create("📊 Server Status", "Current RDU Network Health")
        embed.add_field(name="Discord Members", value=f"`{it.guild.member_count}`", inline=True)
        embed.add_field(name="Rust Pop (Mock)", value="`142/200`", inline=True)
        embed.add_field(name="API Latency", value=f"`{latency}ms`", inline=True)
        
        embed.color = Config.COLOR_SUCCESS if latency < 100 else Config.COLOR_WARNING
        await it.response.send_message(embed=embed)

    @app_commands.command(name="wipe_info", description="Next wipe schedule with local timestamps")
    async def wipe_info(self, it: discord.Interaction):
        # Using Discord Timestamps ensures players see it in their own local time
        # Example timestamp for a future Thursday
        map_wipe = "<t:1712217600:F>" 
        bp_wipe = "First Thursday of every month"
        
        desc = f"📅 **Next Map Wipe:** {map_wipe}\n💀 **BP Wipe:** {bp_wipe}\n\n*Timestamps adjusted to your local timezone.*"
        await it.response.send_message(embed=EmbedFactory.create("📅 Wipe Schedule", desc, Config.COLOR_WARNING))

    @app_commands.command(name="user_info", description="Audit a user's account details")
    async def user_info(self, it: discord.Interaction, member: discord.Member):
        embed = EmbedFactory.create(f"Audit: {member.display_name}", f"ID: `{member.id}`")
        embed.add_field(name="Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await it.response.send_message(embed=embed)

# --- UTILITY COG ---
class Utility(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a simple binary poll")
    async def poll(self, it: discord.Interaction, question: str):
        embed = EmbedFactory.create("📊 Community Poll", question, discord.Color.purple())
        embed.set_author(name=it.user.display_name, icon_url=it.user.display_avatar.url)
        
        await it.response.send_message("Poll deployed.", ephemeral=True)
        msg = await it.channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    @app_commands.command(name="ping", description="Check bot heartbeat")
    async def ping(self, it: discord.Interaction):
        await it.response.send_message(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`", ephemeral=True)

# --- CORE BOT ENGINE ---
class RDUBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # Register Cogs
        await self.add_cog(Moderation(self))
        await self.add_cog(Information(self))
        await self.add_cog(Utility(self))
        
        # Syncing Logic
        if Config.GUILD_ID:
            guild = discord.Object(id=Config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Tree synced for Guild: {Config.GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Tree synced globally")

    async def log_action(self, guild: discord.Guild, embed: discord.Embed):
        channel = discord.utils.get(guild.text_channels, name=Config.LOG_CHANNEL_NAME)
        if channel:
            await channel.send(embed=embed)

    async def on_app_command_error(self, it: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await it.response.send_message("❌ Insufficient permissions to execute this.", ephemeral=True)
        elif isinstance(error, app_commands.CommandOnCooldown):
            await it.response.send_message(f"⏳ On cooldown. Try again in {error.retry_after:.1f}s.", ephemeral=True)
        else:
            logger.error(f"Global Error: {error}")
            if not it.response.is_done():
                await it.response.send_message("⚠️ An internal execution error occurred.", ephemeral=True)

# --- ENTRY POINT ---
async def main():
    bot = RDUBot()
    
    if not Config.TOKEN:
        logger.critical("FATAL: DISCORD_TOKEN is missing from environment.")
        return

    try:
        async with bot:
            await bot.start(Config.TOKEN)
    except Exception as e:
        logger.error(f"Startup failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user.")
