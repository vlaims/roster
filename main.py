import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import time
from functools import wraps
import random
from datetime import datetime, timedelta
import io

# Attempt to import Pillow for Playercards
try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ Pillow not installed. /playercard will fall back to embeds.")

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"
API_CACHE      = {}
CACHE_DURATION = 60  # seconds

# Semaphore for API Queue System (Max 5 concurrent requests)
API_SEMAPHORE = asyncio.Semaphore(5)

# Shop Configuration
SHOP_ITEMS = {
    "booster": {"id": "booster", "name": "XP Booster", "price": 500, "desc": "A temporary role for attention."},
    "custom_color": {"id": "custom_color", "name": "Custom Color", "price": 1000, "desc": "Get a custom colored role."},
    "nitro": {"id": "nitro", "name": "Fake Nitro", "price": 5000, "desc": "A cool role named 'Nitro'"},
    "premium": {"id": "premium", "name": "Premium Status", "price": 10000, "desc": "Top tier role in the server."},
}

# Scrim State
SCRIM_ACTIVE = {
    "active": False,
    "clan_a": None,
    "clan_b": None,
    "map": None,
    "time": None,
    "score_a": 0,
    "score_b": 0
}

# Activity State
ACTIVE_ACTIVITY = {
    "active": False,
    "points": 0,
    "participants": [],
    "starter": None
}

http_session = None

# Tier order — lower index = higher tier
TIER_ORDER      = ["S", "A+", "A", "B", "C", "F"]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}

def tier_rank(tier: str) -> int:
    try: return TIER_ORDER.index(tier.strip())
    except ValueError: return 999

def kirka_headers():
    return {"ApiKey": KIRKA_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}

def supabase_headers():
    key = os.environ.get('SUPABASE_KEY')
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}

def supabase_endpoint(path: str) -> str:
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    return f"{base}/rest/v1/{path}"

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def to_fancy_font(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    return str(text).translate(str.maketrans(normal, fancy))

def make_embed(title, description="", color=discord.Color.from_rgb(63, 207, 142)):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Made by vlaims • api.kirka.io")
    return embed

def get_cached(key):
    data = API_CACHE.get(key)
    if not data: return None
    if time.time() - data["time"] > CACHE_DURATION:
        del API_CACHE[key]
        return None
    return data["value"]

def set_cache(key, value):
    API_CACHE[key] = {"value": value, "time": time.time()}

def cooldown(seconds: int):
    cooldowns = {}
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            now = time.time()
            if user_id in cooldowns:
                remaining = cooldowns[user_id] - now
                if remaining > 0:
                    await interaction.response.send_message(f"⏳ Slow down. Try again in `{remaining:.1f}s`", ephemeral=True)
                    return
            cooldowns[user_id] = now + seconds
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

# ─────────────────────────────────────────────────────────────
# BOT SETUP (Improved for Railway)
# ─────────────────────────────────────────────────────────────
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True # For inactive detection
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        global http_session
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        
        # Sync commands - Guild specific to avoid global rate limits during dev
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        try:
            await self.tree.sync(guild=TEST_GUILD)
            print(f"✅ Synced commands to guild {TEST_GUILD.id}")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")

        # Start Background Tasks
        self.cache_refresher.start()
        self.daily_stats.start()
        
        print(f"✅ Logged in as {self.user}")

    async def close(self):
        self.cache_refresher.cancel()
        self.daily_stats.cancel()
        global http_session
        if http_session: await http_session.close()
        await super().close()

bot = MyBot()

# ─────────────────────────────────────────────────────────────
# BACKGROUND TASKS (Performance)
# ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=10)
async def cache_refresher():
    """Pre-fetches roster data to keep the cache warm."""
    try:
        async with http_session.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                set_cache("full_roster", data)
                print(f"🔄 Cache refreshed at {datetime.now().strftime('%H:%M')}")
    except Exception as e:
        print(f"Cache refresh error: {e}")

@cache_refresher.before_loop
async def before_cache_refresher():
    await bot.wait_until_ready()

@tasks.loop(time=datetime.time(hour=9, minute=0)) # 9 AM Daily
async def daily_stats():
    """Posts daily analytics."""
    # Find a channel named 'general' or 'announcements'
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if not channel: return

    roster = get_cached("full_roster")
    if not roster: return
    
    # Simple logic: find highest PRP
    # Note: This relies on cached data which might be stale, or we force a fetch
    await channel.send("🌅 **Good Morning Clan!** Here is your daily briefing...")
    # Logic to calculate top improver would go here

@daily_stats.before_loop
async def before_daily_stats():
    await bot.wait_until_ready()

# ─────────────────────────────────────────────────────────────
# API HELPERS (With Semaphore)
# ─────────────────────────────────────────────────────────────
async def kirka_get_profile(short_id: str):
    clean_id = short_id.replace('#', '').strip().upper()
    if not clean_id: return None
    cache_key = f"profile:{clean_id}"
    cached = get_cached(cache_key)
    if cached: return cached
    
    async with API_SEMAPHORE:
        try:
            async with http_session.post(
                f"{KIRKA_BASE_URL}/api/user/getProfile",
                headers=kirka_headers(),
                json={"id": clean_id, "isShortId": True}
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    set_cache(cache_key, data)
                    return data
                return None
        except Exception as e:
            print(f"[Kirka] Profile error: {e}")
            return None

async def get_roster_player_by_discord(discord_name: str):
    url = supabase_endpoint(f"roster?discord_handle=eq.{discord_name}&select=*")
    try:
        async with http_session.get(url, headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
            return None
    except Exception: return None

async def get_roster_player_by_name(name: str):
    url = supabase_endpoint(f"roster?name=ilike.{name}&select=*")
    try:
        async with http_session.get(url, headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
            return None
    except Exception: return None

async def update_player_points(player_name: str, new_points: float):
    url = supabase_endpoint(f"roster?name=eq.{player_name}")
    try:
        async with http_session.patch(url, headers=supabase_headers(), json={"points": round(new_points, 2)}) as resp:
            return resp.status in [200, 204]
    except Exception: return False

async def roster_autocomplete(interaction: discord.Interaction, current: str):
    roster = get_cached("full_roster") or []
    suggestions = []
    current_lower = current.lower()
    for player in roster[:25]: # Limit autocomplete search
        name = player.get("name", "")
        if current_lower in name.lower():
            suggestions.append(app_commands.Choice(name=name, value=name))
    return suggestions[:25]

# ─────────────────────────────────────────────────────────────
# VIEWS & UI
# ─────────────────────────────────────────────────────────────
class PaginationView(discord.ui.View):
    def __init__(self, pages: list, title: str, total_label: str = ""):
        super().__init__(timeout=180)
        self.pages = pages
        self.title = title
        self.total_label = total_label
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page == len(self.pages) - 1

    def create_embed(self):
        desc = (f"### {self.total_label}\n\n" if self.total_label else "") + self.pages[self.current_page]
        embed = discord.Embed(title=self.title, description=desc, color=discord.Color.from_rgb(63, 207, 142))
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)} | Made by vlaims")
        return embed

    @discord.ui.button(label="<--", style=discord.ButtonStyle.green)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.edit_original_response(embed=self.create_embed(), view=self)

    @discord.ui.button(label="-->", style=discord.ButtonStyle.green)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.edit_original_response(embed=self.create_embed(), view=self)

# Scrim View
class ScrimView(discord.ui.View):
    def __init__(self, clan_a, clan_b):
        super().__init__(timeout=None)
        self.clan_a = clan_a
        self.clan_b = clan_b
        self.score_a = 0
        self.score_b = 0

    def update_embed(self):
        return discord.Embed(
            title=f"⚔️ LIVE SCRIM: {self.clan_a} vs {self.clan_b}",
            description=f"**Score:** {self.score_a} - {self.score_b}",
            color=discord.Color.red()
        )

    @discord.ui.button(label=f"{clan_a} +1", style=discord.ButtonStyle.blurple)
    async def score_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.score_a += 1
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label=f"{clan_b} +1", style=discord.ButtonStyle.blurple)
    async def score_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.score_b += 1
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="End Scrim", style=discord.ButtonStyle.red)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Log result to DB (mockup here)
        await interaction.response.edit_message(content=f"🏁 Final Score: {self.score_a} - {self.score_b}", embed=None, view=None)

# Poll View
class PollView(discord.ui.View):
    def __init__(self, question):
        super().__init__(timeout=None)
        self.question = question
        self.votes = {"Yes": 0, "No": 0}

    async def update_count(self, interaction, choice):
        self.votes[choice] += 1
        await interaction.response.edit_message(content=f"**{self.question}**\n👍 Yes: {self.votes['Yes']}\n👎 No: {self.votes['No']}")

    @discord.ui.button(emoji="👍", style=discord.ButtonStyle.green)
    async def yes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_count(interaction, "Yes")

    @discord.ui.button(emoji="👎", style=discord.ButtonStyle.red)
    async def no_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_count(interaction, "No")

# ─────────────────────────────────────────────────────────────
# NEW COMPETITIVE COMMANDS
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="scrim", description="Start a scrim tracker")
@app_commands.describe(clan="Opposing clan name", map="Map name")
async def scrim(interaction: discord.Interaction, clan: str, map: str):
    if SCRIM_ACTIVE["active"]:
        await interaction.response.send_message("A scrim is already active!", ephemeral=True)
        return
    
    SCRIM_ACTIVE["active"] = True
    SCRIM_ACTIVE["clan_b"] = clan
    SCRIM_ACTIVE["map"] = map
    
    view = ScrimView("KISS", clan)
    embed = view.update_embed()
    embed.add_field(name="Map", value=map)
    embed.add_field(name="Time", value=datetime.now().strftime("%H:%M"))
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="elo", description="Calculate ELO change for a match")
@app_commands.describe(winner="Winner name", loser="Loser name", k_factor="K-Factor (default 32)")
async def elo(interaction: discord.Interaction, winner: str, loser: str, k_factor: int = 32):
    # Simplified ELO
    # Ra' = Ra + K(Sa - Ea)
    # If A wins, Sa=1, Sb=0. Ea = 1 / (1 + 10 ^ ((Rb-Ra)/400))
    # Assuming starting ELO of 1200 for both if unknown (for this demo)
    
    Ra = 1200 
    Rb = 1200
    
    Ea = 1 / (1 + 10 ** ((Rb - Ra) / 400))
    Eb = 1 / (1 + 10 ** ((Ra - Rb) / 400))
    
    new_ra = Ra + k_factor * (1 - Ea)
    new_rb = Rb + k_factor * (0 - Eb)
    
    embed = make_embed("📊 ELO Calculation")
    embed.add_field(name=winner, value=f"+{new_ra - Ra:.1f} (New: {new_ra:.0f})", inline=True)
    embed.add_field(name=loser, value=f"{new_rb - Rb:.1f} (New: {new_rb:.0f})", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="topheadshots", description="Leaderboard for headshots")
async def topheadshots(interaction: discord.Interaction):
    await interaction.response.defer()
    # This requires iterating profiles, might be slow.
    # In production, store this in DB
    roster = get_cached("full_roster") or []
    
    results = []
    # Limit to first 10 to avoid timeout
    for p in roster[:15]: 
        profile = await kirka_get_profile(p.get('player_id'))
        if profile:
            hs = profile.get('stats', {}).get('headshots', 0)
            results.append((p['name'], hs))
            
    results.sort(key=lambda x: x[1], reverse=True)
    text = "\n".join([f"**{i+1}.** {to_fancy_font(n)} — `{hs:,}`" for i, (n, hs) in enumerate(results[:5])])
    await interaction.followup.send(embed=make_embed("🎯 Top Headshots", text))

@bot.tree.command(name="playercard", description="Generate a profile card (Requires Pillow)")
@app_commands.describe(name="Player name")
@app_commands.autocomplete(name=roster_autocomplete)
async def playercard(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    player = await get_roster_player_by_name(name)
    if not player:
        await interaction.followup.send("Player not found.", ephemeral=True)
        return
        
    profile = await kirka_get_profile(player['player_id'])
    
    if PILLOW_AVAILABLE:
        # Generate Image
        width, height = 400, 200
        img = Image.new('RGB', (width, height), color=(30, 30, 30))
        d = ImageDraw.Draw(img)
        
        # Load font (using default if file not found)
        try:
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw Data
        d.text((20, 20), f"NAME: {player['name'].upper()}", fill=(255, 255, 255), font=font_large)
        
        if profile:
            stats = profile.get('stats', {})
            kd = round(stats.get('kills', 0)/max(stats.get('deaths', 1), 1), 2)
            d.text((20, 60), f"KD: {kd}", fill=(100, 255, 100), font=font_small)
            d.text((150, 60), f"WINS: {stats.get('wins', 0)}", fill=(100, 200, 255), font=font_small)
            d.text((20, 90), f"PRP: {profile.get('klo2V2', 0)}", fill=(255, 200, 50), font=font_small)
        
        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        file = discord.File(buffer, filename="card.png")
        
        await interaction.followup.send(file=file)
    else:
        # Fallback to Embed
        if profile:
            stats = profile.get('stats', {})
            kd = round(stats.get('kills', 0)/max(stats.get('deaths', 1), 1), 2)
            desc = f"KD: `{kd}` | Wins: `{stats.get('wins', 0)}`"
            await interaction.followup.send(embed=make_embed(player['name'], desc))

# ─────────────────────────────────────────────────────────────
# SMART & ANALYTICS COMMANDS
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="analytics", description="Server-wide clan analytics")
async def analytics(interaction: discord.Interaction):
    await interaction.response.defer()
    roster = get_cached("full_roster") or []
    
    total_pts = sum([float(p.get('points', 0)) for p in roster])
    avg_pts = total_pts / len(roster) if roster else 0
    
    # Calculate average KD (fetching profiles might take time, sample first 10)
    kds = []
    for p in roster[:10]:
        prof = await kirka_get_profile(p['player_id'])
        if prof:
            s = prof.get('stats', {})
            kds.append(s.get('kills',0)/max(s.get('deaths',1),1))
            
    avg_kd = sum(kds)/len(kds) if kds else 0
    
    embed = make_embed("📊 Clan Analytics")
    embed.add_field(name="Total Members", value=len(roster))
    embed.add_field(name="Avg Points", value=f"{avg_pts:,.2f}")
    embed.add_field(name="Avg KD (Sample)", value=f"{avg_kd:.2f}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="poll", description="Create a vote")
@app_commands.describe(question="What to vote on")
async def poll_cmd(interaction: discord.Interaction, question: str):
    view = PollView(question)
    await interaction.response.send_message(f"**{question}**", view=view)

# ─────────────────────────────────────────────────────────────
# FUN & GAMBLING
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="gamble", description="Gamble your clan points")
@app_commands.describe(amount="Amount to bet")
async def gamble(interaction: discord.Interaction, amount: float):
    await interaction.response.defer()
    player = await get_roster_player_by_discord(interaction.user.name)
    if not player:
        await interaction.followup.send("You aren't on the roster.", ephemeral=True)
        return
        
    current = float(player.get('points', 0))
    if amount > current:
        await interaction.followup.send("You're too broke!", ephemeral=True)
        return
        
    roll = random.randint(1, 100)
    if roll > 50:
        new = current + amount
        await update_player_points(player['name'], new)
        await interaction.followup.send(f"🎉 You rolled {roll}! You won `{amount}` pts! New Balance: `{new}`")
    else:
        new = current - amount
        await update_player_points(player['name'], new)
        await interaction.followup.send(f"💀 You rolled {roll}. You lost `{amount}` pts. New Balance: `{new}`")

@bot.tree.command(name="expose", description="Expose a member")
@app_commands.describe(member="Who to expose")
async def expose(interaction: discord.Interaction, member: discord.Member):
    roasts = [
        "Grass touched: 0 times this year",
        "Showers taken: 3 (debated)",
        "Social battery: 1%",
        "Skill issue: Detected",
        "Time spent outside: 0 hours",
        "Sunlight allergy: Confirmed"
    ]
    fact = random.choice(roasts)
    await interaction.response.send_message(f"🔍 **Exposing {member.display_name}...**\n❗ {fact}")

@bot.tree.command(name="cook", description="Roast someone")
@app_commands.describe(target="Who to cook")
async def cook(interaction: discord.Interaction, target: str):
    await interaction.response.send_message(f"🍳 **Cooking {target}...**\n\nYou're so bad at Kirka, the devs refunded your Premium rank.")

# ─────────────────────────────────────────────────────────────
# EXISTING COMMANDS & SYSTEMS (Preserved)
# ─────────────────────────────────────────────────────────────

class ChallengeResultView(discord.ui.View):
    def __init__(self, challenger_data, opponent_data, bet, challenger_member, opponent_member):
        super().__init__(timeout=300)
        self.challenger_data, self.opponent_data = challenger_data, opponent_data
        self.bet, self.challenger_member, self.opponent_member = bet, challenger_member, opponent_member
        self.resolved = False

    def calculate_payout(self, winner_data, loser_data) -> float:
        return round(self.bet * TIER_MULTIPLIER.get(winner_data.get("tier", "F").strip(), 1.0), 2)

    async def resolve(self, interaction, winner_member, loser_member, winner_data, loser_data):
        if self.resolved: return
        self.resolved = True
        payout = self.calculate_payout(winner_data, loser_data)
        
        # Update Points
        winner_new = float(winner_data.get("points", 0)) + payout
        loser_new = max(0, float(loser_data.get("points", 0)) - self.bet)
        
        await update_player_points(winner_data["name"], winner_new)
        await update_player_points(loser_data["name"], loser_new)
        
        embed = discord.Embed(title="⚔️ Challenge Result", color=discord.Color.gold())
        embed.add_field(name="🏆 Winner", value=f"{winner_member.mention} (+{payout})", inline=False)
        embed.add_field(name="💀 Loser", value=f"{loser_member.mention} (-{self.bet})", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Challenger Won", style=discord.ButtonStyle.green)
    async def c_won(self, i: discord.Interaction, b: discord.ui.Button):
        if "leader" not in [r.name for r in i.user.roles]:
            await i.response.send_message("Leaders only.", ephemeral=True); return
        await self.resolve(i, self.challenger_member, self.opponent_member, self.challenger_data, self.opponent_data)

    @discord.ui.button(label="Opponent Won", style=discord.ButtonStyle.blurple)
    async def o_won(self, i: discord.Interaction, b: discord.ui.Button):
        if "leader" not in [r.name for r in i.user.roles]:
            await i.response.send_message("Leaders only.", ephemeral=True); return
        await self.resolve(i, self.opponent_member, self.challenger_member, self.opponent_data, self.challenger_data)

class ChallengeAcceptView(discord.ui.View):
    def __init__(self, challenger_data, opponent_data, bet, challenger_member, opponent_member):
        super().__init__(timeout=120)
        self.c_data, self.o_data, self.bet = challenger_data, opponent_data, bet
        self.c_mem, self.o_mem = challenger_member, opponent_member

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.o_mem.id: return
        await i.response.edit_message(view=ChallengeResultView(self.c_data, self.o_data, self.bet, self.c_mem, self.o_mem))

@bot.tree.command(name="challenge", description="Challenge a member")
@app_commands.describe(opponent="Member", bet="Points")
async def challenge(i: discord.Interaction, opponent: discord.Member, bet: float):
    await i.response.defer()
    if bet <= 0: await i.followup.send("Invalid bet", ephemeral=True); return
    
    c_data = await get_roster_player_by_discord(i.user.name)
    o_data = await get_roster_player_by_discord(opponent.name)
    
    if not c_data or not o_data: await i.followup.send("Roster lookup failed.", ephemeral=True); return
    if float(c_data.get('points',0)) < bet or float(o_data.get('points',0)) < bet:
        await i.followup.send("Someone is too broke.", ephemeral=True); return

    view = ChallengeAcceptView(c_data, o_data, bet, i.user, opponent)
    await i.followup.send(f"⚔️ {i.user.mention} vs {opponent.mention} for `{bet}` pts", view=view)

@bot.tree.command(name="members", description="View roster")
async def members(i: discord.Interaction):
    await i.response.defer()
    roster = get_cached("full_roster")
    if not roster:
        async with http_session.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as resp:
            roster = await resp.json() if resp.status == 200 else []
            
    lines = [f"**{p['name']}** | Tier: {p.get('tier', '?')} | Pts: {p.get('points',0)}" for p in roster]
    pages = ["\n".join(lines[j:j+10]) for j in range(0, len(lines), 10)]
    view = PaginationView(pages, "Kiss Clan Roster")
    await i.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="points", description="Check points")
@app_commands.autocomplete(name=roster_autocomplete)
async def points(i: discord.Interaction, name: str = None):
    await i.response.defer()
    p = await get_roster_player_by_name(name) if name else await get_roster_player_by_discord(i.user.name)
    if p:
        await i.followup.send(embed=make_embed(f"💰 {p['name']}", f"Tier: `{p.get('tier','?')}`\nPoints: `{p.get('points',0):,.2f}`"))
    else:
        await i.followup.send("Player not found", ephemeral=True)

@bot.tree.command(name="settier", description="Set tier (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.autocomplete(name=roster_autocomplete)
async def settier(i: discord.Interaction, name: str, tier: str):
    if tier not in TIER_ORDER: await i.response.send_message("Invalid Tier", ephemeral=True); return
    url = supabase_endpoint(f"roster?name=ilike.{name}")
    async with http_session.patch(url, headers=supabase_headers(), json={"tier": tier}) as resp:
        if resp.status in [200, 204]: await i.response.send_message(f"Updated {name} to {tier}", ephemeral=True)
        else: await i.response.send_message("Failed", ephemeral=True)

@bot.tree.command(name="profile", description="Kirka Profile")
@app_commands.autocomplete(player_id=roster_autocomplete)
async def profile(i: discord.Interaction, player_id: str):
    await i.response.defer()
    # Check roster first for ID
    roster = get_cached("full_roster") or []
    player = next((p for p in roster if p['name'].lower() == player_id.lower()), None)
    if player: player_id = player['player_id']
    
    data = await kirka_get_profile(player_id)
    if not data: await i.followup.send("Not found"); return
    
    stats = data.get('stats', {})
    kd = round(stats.get('kills',0)/max(stats.get('deaths',1),1),2)
    embed = discord.Embed(title=data.get('name'), description=f"#{data.get('shortId')}", color=discord.Color.green())
    embed.add_field(name="KD", value=kd); embed.add_field(name="PRP", value=data.get('klo2V2',0))
    await i.followup.send(embed=embed)

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in: {bot.user}")
    print("=" * 50)

@bot.tree.error
async def on_command_error(i: discord.Interaction, e):
    if i.response.is_done():
        if i.is_done(): await i.followup.send(f"Error: {e}", ephemeral=True)
    else:
        await i.response.send_message(f"Error: {e}", ephemeral=True)

# Run
for v in ["DISCORD_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]:
    if not os.environ.get(v): raise RuntimeError(f"Missing {v}")

bot.run(os.environ.get('DISCORD_TOKEN'))