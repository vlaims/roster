import os
import sys
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import random
import logging
from datetime import datetime, timedelta, time

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"
SUPABASE_URL   = os.environ.get('SUPABASE_URL')
SUPABASE_KEY   = os.environ.get('SUPABASE_KEY')
LOGS_CHANNEL_ID = int(os.environ.get('LOGS_CHANNEL_ID', 0))

# Economy Config
TIER_ORDER      = ["S", "A+", "A", "B", "C", "F"]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}
XP_RATE         = 10
LEVEL_UP_XP     = 1000
DAILY_REWARD    = 500

# State
ACTIVE_EVENTS = {}

# ─────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────
def kirka_headers():
    return {"ApiKey": KIRKA_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}

def supabase_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

def supabase_endpoint(path: str) -> str:
    return f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path}"

def to_fancy_font(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    return str(text).translate(str.maketrans(normal, fancy))

# ─────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────
async def get_roster_member(name: str):
    url = supabase_endpoint(f"roster?name=eq.{name}&select=*")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=supabase_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0] if data else None
    except Exception as e: print(f"DB Error fetching {name}: {e}")
    return None

async def update_roster_member(name: str, data: dict):
    url = supabase_endpoint(f"roster?name=eq.{name}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=supabase_headers(), json=data) as resp:
                return resp.status in [200, 204]
    except Exception as e: 
        print(f"DB Error updating {name}: {e}")
        return False

async def log_action(action: str, user: str, details: str):
    print(f"[LOG] {action} | {user}: {details}")
    url = supabase_endpoint("logs")
    payload = {"action": action, "user_name": user, "details": details}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, headers=supabase_headers(), json=payload)
    except: pass

async def add_points(name: str, amount: int, reason: str = "System"):
    member = await get_roster_member(name)
    if not member: return
    current_pts = member.get('points', 0) + amount
    await update_roster_member(name, {"points": current_pts})
    await log_action("ECONOMY", name, f"{amount:+} pts ({reason}). New Balance: {current_pts}")

async def add_xp(name: str, amount: int):
    member = await get_roster_member(name)
    if not member: return
    current_xp = member.get('xp', 0) + amount
    current_lvl = member.get('level', 1)
    new_level = int(current_xp / LEVEL_UP_XP) + 1
    await update_roster_member(name, {"xp": current_xp, "level": new_level})

# ─────────────────────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────────────────────
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Switching to Global Sync to ensure commands work everywhere
        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} commands globally.")
        except Exception as e:
            print(f"❌ Sync failed: {e}")
        
        self.daily_leaderboard_task.start()
        self.auto_sync_stats.start()
        self.weekly_reset_check.start()

bot = MyBot()

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🚀 Logged in as {bot.user}")
    print(f"📡 Connected to {len(bot.guilds)} servers")
    print("=" * 50)

# ─────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=10)
async def auto_sync_stats():
    pass 

@tasks.loop(time=time(hour=9, minute=0))
async def daily_leaderboard_task():
    if LOGS_CHANNEL_ID:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            await channel.send("📊 **Daily Leaderboard Reset!**")

@tasks.loop(hours=1)
async def weekly_reset_check():
    now = datetime.now()
    if now.weekday() == 0 and now.hour == 0 and now.minute == 0:
        await log_action("SYSTEM", "Bot", "Weekly Reset.")

# ─────────────────────────────────────────────────────────────
# KIRKA API HELPERS
# ─────────────────────────────────────────────────────────────
async def kirka_get_profile(short_id: str):
    clean_id = short_id.replace('#', '').strip()
    if not clean_id: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{KIRKA_BASE_URL}/api/user/getProfile",
                headers=kirka_headers(),
                json={"id": clean_id, "isShortId": True},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 201: return await resp.json()
    except Exception: pass
    return None

async def kirka_get_clan(clan_name: str):
    """Missing function added back."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KIRKA_BASE_URL}/api/clan/{clan_name}",
                headers=kirka_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200: return await resp.json()
    except Exception: pass
    return None

async def kirka_get_ranked2v2():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KIRKA_BASE_URL}/api/leaderboard/ranked2V2",
                headers=kirka_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200: return await resp.json()
    except Exception: pass
    return None

# ─────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────
class PaginationView(discord.ui.View):
    def __init__(self, pages: list, title: str, total_label: str = ""):
        super().__init__(timeout=180)
        self.pages = pages
        self.title = title
        self.total_label = total_label
        self.current_page = 0
        self.prev_btn.disabled = True
        if len(self.pages) <= 1: self.next_btn.disabled = True

    def create_embed(self):
        desc = (f"### {self.total_label}\n\n" if self.total_label else "") + self.pages[self.current_page]
        embed = discord.Embed(title=self.title, description=desc, color=discord.Color.from_rgb(63, 207, 142))
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)} | Made by vlaims")
        return embed

    @discord.ui.button(label="<--", style=discord.ButtonStyle.green)
    async def prev_btn(self, i, b):
        await i.response.defer()
        if self.current_page > 0: self.current_page -= 1
        self.next_btn.disabled = False
        if self.current_page == 0: b.disabled = True
        await i.edit_original_response(embed=self.create_embed(), view=self)

    @discord.ui.button(label="-->", style=discord.ButtonStyle.green)
    async def next_btn(self, i, b):
        await i.response.defer()
        if self.current_page < len(self.pages) - 1: self.current_page += 1
        self.prev_btn.disabled = False
        if self.current_page == len(self.pages) - 1: b.disabled = True
        await i.edit_original_response(embed=self.create_embed(), view=self)

# ─────────────────────────────────────────────────────────────
# COMMANDS: ECONOMY
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="balance", description="Check your points and XP")
async def balance(i: discord.Interaction):
    await i.response.defer()
    member = await get_roster_member(i.user.name)
    if not member:
        await i.followup.send("You are not in the roster.", ephemeral=True)
        return
    embed = discord.Embed(title=f"💰 {i.user.display_name}'s Wallet", color=discord.Color.gold())
    embed.add_field(name="Points", value=f"`{member.get('points', 0):,}`", inline=True)
    embed.add_field(name="XP", value=f"`{member.get('xp', 0):,}`", inline=True)
    embed.add_field(name="Level", value=f"`{member.get('level', 1)}`", inline=True)
    await i.followup.send(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily reward")
async def daily(i: discord.Interaction):
    await i.response.defer()
    await add_points(i.user.name, DAILY_REWARD, "Daily Reward")
    await i.followup.send(f"✅ You claimed your daily `{DAILY_REWARD}` points!")

@bot.tree.command(name="coinflip", description="Flip a coin for points")
@app_commands.describe(amount="Amount to bet", choice="heads or tails")
async def coinflip(i: discord.Interaction, amount: int, choice: str):
    await i.response.defer()
    member = await get_roster_member(i.user.name)
    if not member or member.get('points', 0) < amount:
        await i.followup.send("You don't have enough points.", ephemeral=True)
        return
    result = random.choice(["heads", "tails"])
    if result.lower() == choice.lower():
        await add_points(i.user.name, amount, "Coinflip Win")
        await i.followup.send(f"🪙 It was **{result}**! You won `{amount}` points!")
    else:
        await add_points(i.user.name, -amount, "Coinflip Loss")
        await i.followup.send(f"🪙 It was **{result}**. You lost `{amount}` points.")

@bot.tree.command(name="shop", description="View the reward shop")
async def shop(i: discord.Interaction):
    await i.response.defer()
    embed = discord.Embed(title="🛒 Clan Shop", color=discord.Color.purple())
    embed.add_field(name="Role: Booster", value="500 pts", inline=False)
    embed.add_field(name="Role: Nitro", value="1000 pts", inline=False)
    await i.followup.send(embed=embed)

# ─────────────────────────────────────────────────────────────
# COMMANDS: COMPETITIVE
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="record_win", description="Admin command to record a win")
@app_commands.describe(winner="Winner Name", loser="Loser Name")
async def record_win(i: discord.Interaction, winner: str, loser: str):
    await i.response.defer()
    await add_points(winner, 100, f"Win vs {loser}")
    await add_points(loser, -50, f"Loss vs {winner}")
    await add_xp(winner, 500)
    await add_xp(loser, 100)
    await i.followup.send(f"✅ Recorded win for {winner}.")

# ─────────────────────────────────────────────────────────────
# COMMANDS: ORIGINAL
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="members", description="View roster")
async def members(i: discord.Interaction):
    await i.response.defer()
    target_endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/roster?select=*&order=name.desc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(target_endpoint, headers=headers) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    lines = [f"**{x['name']}** | Pts: {x.get('points', 0)}" for x in raw_data]
                    pages = ["\n".join(lines[j:j+10]) for j in range(0, len(lines), 10)]
                    view = PaginationView(pages, "Roster")
                    await i.followup.send(embed=view.create_embed(), view=view)
    except Exception as e: await i.followup.send(f"Error: {e}")

@bot.tree.command(name="profile", description="Look up a Kirka profile")
@app_commands.describe(player_id="Short ID")
async def profile(i: discord.Interaction, player_id: str):
    await i.response.defer()
    data = await kirka_get_profile(player_id)
    if not data: await i.followup.send("Not found"); return
    stats = data.get('stats', {})
    kd = round(stats.get('kills',0)/max(stats.get('deaths',1),1),2)
    embed = discord.Embed(title=data.get('name'), description=f"#{data.get('shortId')}", color=discord.Color.green())
    embed.add_field(name="KD", value=kd)
    embed.add_field(name="PRP", value=data.get('klo2V2',0))
    await i.followup.send(embed=embed)

@bot.tree.command(name="prp", description="Ranked 2v2 Leaderboard")
async def prp(i: discord.Interaction):
    await i.response.defer()
    data = await kirka_get_ranked2v2()
    if not data: await i.followup.send("API Error"); return
    results = data.get('results', [])
    lines = [f"**{x.get('name')}** PRP: {x.get('klo2V2')}" for x in results[:10]]
    await i.followup.send("\n".join(lines))

@bot.event
async def on_message(message):
    if message.author.bot: return
    if random.random() < 0.1: await add_xp(message.author.name, XP_RATE)

bot.run(os.environ.get('DISCORD_TOKEN'))