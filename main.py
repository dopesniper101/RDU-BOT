import os
import logging
import discord
import asyncio
from datetime import datetime
from typing import Final, Optional, Union
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client

# --- CONFIGURATION ---
class Config:
    # Discord
    TOKEN: Final = os.environ.get('DISCORD_TOKEN')
    GUILD_ID: Final = int(os.environ.get('GUILD_ID', 1468873461207142556))
    ADMIN_ROLE_ID: Final = 1095005926534168646
    LOG_CHANNEL_NAME: Final = "bot-logs"
    VERSION: Final = "v3.1.0-PRO"
    BOT_NAME: Final = "RUST DOWN UNDER"

    # Supabase (Injected from your provided credentials)
    SUPABASE_URL: Final = "https://mstmpktndqddfzsrumek.supabase.co"
    SUPABASE_KEY: Final = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s: %(message)s')
logger = logging.getLogger("RDU_CORE")

# --- UI FACTORY ---
class EmbedFactory:
    @staticmethod
    def build(title: str, description: str, color: discord.Color = discord.Color.blue(), thumb: str = None) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
        embed.set_footer(text=f"{Config.BOT_NAME} | {Config.VERSION}")
        if thumb:
            embed.set_thumbnail(url=thumb)
        return embed

# --- DATA ACCESS LAYER ---
class SupabaseManager:
    def __init__(self):
        self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    async def log_audit(self, mod_id: int, action: str, target_id: Optional[int], reason: str):
        """Saves moderation actions to Supabase."""
        data = {
            "moderator_id": str(mod_id),
            "action": action,
            "target_id": str(target_id) if target_id else None,
            "reason": reason
        }
        # Run in thread to prevent blocking the event loop
        return await asyncio.to_thread(self.client.table("audit_logs").insert(data).execute)

    async def get_config(self, key: str) -> Optional[str]:
        """Retrieves dynamic config (like wipe dates) from Supabase."""
        res = await asyncio.to_thread(self.client.table("server_config").select("value").eq("key", key).maybe_single().execute)
        return res.data['value'] if res.data else None

# --- COGS ---
class Moderation(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="ban", description="Ban a member and log to Database")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, it: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= it.user.top_role:
            return await it.response.send_message("❌ Cannot ban users with higher/equal roles.", ephemeral=True)
        
        await member.ban(reason=reason)
        await self.bot.db.log_audit(it.user.id, "BAN", member.id, reason)
        
        embed = EmbedFactory.build("🔨 Member Banned", f"Target: {member.mention}\nReason: {reason}", discord.Color.red())
        await it.response.send_message(embed=embed)
        await self.bot.dispatch_log(it.guild, embed)

    @app_commands.command(name="clear", description="Bulk delete messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, it: discord.Interaction, amount: int):
        if not 1 <= amount <= 100:
            return await it.response.send_message("❌ Range 1-100 only.", ephemeral=True)
        await it.response.defer(ephemeral=True)
        deleted = await it.channel.purge(limit=amount)
        await it.edit_original_response(content=f"🧹 Purged {len(deleted)} messages.")

class Information(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="wipe_info", description="Get wipe schedule (Stored in Supabase)")
    async def wipe_info(self, it: discord.Interaction):
        await it.response.defer()
        unix_timestamp = await self.bot.db.get_config("next_wipe")
        
        # UI utilizes Discord's dynamic timestamp format <t:UNIX:F>
        wipe_display = f"<t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)" if unix_timestamp else "Not Set"
        
        desc = f"📅 **Next Map Wipe:** {wipe_display}\n💀 **BP Wipe:** First Thursday of Month"
        await it.followup.send(embed=EmbedFactory.build("📅 Wipe Schedule", desc, discord.Color.gold()))

    @app_commands.command(name="user_info", description="Audit user account age and roles")
    async def user_info(self, it: discord.Interaction, member: discord.Member):
        embed = EmbedFactory.build(f"Audit: {member.display_name}", f"ID: `{member.id}`", thumb=member.display_avatar.url)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=False)
        await it.response.send_message(embed=embed)

class Utility(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="ping", description="Network heartbeat")
    async def ping(self, it: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 100 else discord.Color.red()
        await it.response.send_message(embed=EmbedFactory.build("🏓 Pong!", f"Latency: **{latency}ms**", color))

# --- CORE BOT ---
class RDUBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        
        # Initialize Supabase Layer
        self.db = SupabaseManager()

    async def setup_hook(self):
        # Register Cogs
        await self.add_cog(Moderation(self))
        await self.add_cog(Information(self))
        await self.add_cog(Utility(self))
        
        # Syncing
        guild = discord.Object(id=Config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info(f"Bot Tree Synced to {Config.GUILD_ID}")

    async def dispatch_log(self, guild: discord.Guild, embed: discord.Embed):
        channel = discord.utils.get(guild.text_channels, name=Config.LOG_CHANNEL_NAME)
        if channel:
            await channel.send(embed=embed)

    async def on_app_command_error(self, it: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await it.response.send_message("❌ You lack permissions for this.", ephemeral=True)
        else:
            logger.error(f"Execution Error: {error}")

# --- BOOT ---
async def main():
    bot = RDUBot()
    if not Config.TOKEN:
        logger.critical("MISSING DISCORD_TOKEN.")
        return
    
    async with bot:
        await bot.start(Config.TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown initiated.")
