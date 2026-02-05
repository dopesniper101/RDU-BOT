import os
import logging
import discord
import asyncio
from datetime import datetime
from typing import Final, Optional
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client

# --- CONFIGURATION ---
class Config:
    TOKEN: Final = os.environ.get('DISCORD_TOKEN')
    GUILD_ID: Final = int(os.environ.get('GUILD_ID', 1468873461207142556))
    
    # Supabase Credentials
    SUPABASE_URL: Final = "https://mstmpktndqddfzsrumek.supabase.co"
    SUPABASE_KEY: Final = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', "") # Use your key here
    
    LOG_CHANNEL_NAME: Final = "bot-logs"
    VERSION: Final = "v3.2.0-STABLE"
    BOT_NAME: Final = "RUST DOWN UNDER"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("RDU_CORE")

# --- DATA ACCESS LAYER ---
class SupabaseManager:
    def __init__(self):
        try:
            self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            logger.info("Supabase Connection Initialized.")
        except Exception as e:
            logger.error(f"Supabase Init Failed: {e}")

    async def log_audit(self, mod_id: int, action: str, target_id: Optional[int], reason: str):
        data = {"moderator_id": str(mod_id), "action": action, "target_id": str(target_id), "reason": reason}
        return await asyncio.to_thread(self.client.table("audit_logs").insert(data).execute)

    async def get_config(self, key: str) -> Optional[str]:
        try:
            res = await asyncio.to_thread(self.client.table("server_config").select("value").eq("key", key).maybe_single().execute)
            return res.data['value'] if res and res.data else None
        except Exception as e:
            logger.error(f"Supabase Query Error: {e}")
            return None

# --- UI FACTORY ---
class EmbedFactory:
    @staticmethod
    def build(title: str, description: str, color: discord.Color = discord.Color.blue(), thumb: str = None) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
        embed.set_footer(text=f"{Config.BOT_NAME} | {Config.VERSION}")
        if thumb: embed.set_thumbnail(url=thumb)
        return embed

# --- COGS ---
class Moderation(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="ban", description="Ban a member and log to DB")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, it: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        # 1. Immediate Deferral (Prevents "Application did not respond")
        await it.response.defer(ephemeral=False)
        
        if member.top_role >= it.user.top_role:
            return await it.followup.send("❌ You cannot ban this user (Role Hierarchy).")
        
        try:
            await member.ban(reason=reason)
            await self.bot.db.log_audit(it.user.id, "BAN", member.id, reason)
            
            embed = EmbedFactory.build("🔨 Ban Successful", f"**Target:** {member.mention}\n**Reason:** {reason}", discord.Color.red())
            await it.followup.send(embed=embed)
            await self.bot.dispatch_log(it.guild, embed)
        except Exception as e:
            await it.followup.send(f"⚠️ Error executing ban: {e}")

    @app_commands.command(name="clear", description="Bulk delete messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, it: discord.Interaction, amount: int):
        if not 1 <= amount <= 100:
            return await it.response.send_message("❌ Use 1-100.", ephemeral=True)
        
        await it.response.defer(ephemeral=True)
        deleted = await it.channel.purge(limit=amount)
        await it.edit_original_response(content=f"🧹 Purged {len(deleted)} messages.")

class Information(commands.Cog):
    def __init__(self, bot: 'RDUBot'):
        self.bot = bot

    @app_commands.command(name="wipe_info", description="Check next wipe schedule")
    async def wipe_info(self, it: discord.Interaction):
        # Defer because DB calls can be slow
        await it.response.defer()
        
        unix_ts = await self.bot.db.get_config("next_wipe")
        wipe_display = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)" if unix_ts else "Check #announcements"
        
        embed = EmbedFactory.build("📅 Wipe Schedule", f"**Next Map Wipe:** {wipe_display}\n**BP Wipe:** Monthly", discord.Color.gold())
        await it.followup.send(embed=embed)

    @app_commands.command(name="user_info", description="View account history")
    async def user_info(self, it: discord.Interaction, member: discord.Member):
        await it.response.defer()
        embed = EmbedFactory.build(f"User: {member.display_name}", f"ID: `{member.id}`", thumb=member.display_avatar.url)
        embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        await it.followup.send(embed=embed)

# --- CORE BOT ---
class RDUBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.db = SupabaseManager()

    async def setup_hook(self):
        await self.add_cog(Moderation(self))
        await self.add_cog(Information(self))
        
        guild = discord.Object(id=Config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info(f"Commands synced to Guild {Config.GUILD_ID}")

    async def dispatch_log(self, guild: discord.Guild, embed: discord.Embed):
        channel = discord.utils.get(guild.text_channels, name=Config.LOG_CHANNEL_NAME)
        if channel: await channel.send(embed=embed)

    async def on_ready(self):
        logger.info(f"✅ {self.user.name} is online and connected to Supabase.")

# --- START ---
async def main():
    if not Config.TOKEN:
        print("Error: DISCORD_TOKEN not found.")
        return
    
    bot = RDUBot()
    async with bot:
        await bot.start(Config.TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
