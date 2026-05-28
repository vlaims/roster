import os
import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import time
import random
import logging
import io
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout, 
    force=True
)
log = logging.getLogger("RailwayBot")

# ─────────────────────────────────────────────────────────────
# ENVIRONMENT CHECKS
# ─────────────────────────────────────────────────────────────
DISCORD_TOKEN  = os.environ.get('DISCORD_TOKEN')
SUPABASE_URL   = os.environ.get('SUPABASE_URL')
SUPABASE_KEY   = os.environ.get('SUPABASE_KEY')
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY')

log.info("Checking Environment Variables...")
if not DISCORD_TOKEN:
    log.critical("❌ CRASH: DISCORD_TOKEN is missing.")
    sys.exit(1)
if not SUPABASE_URL:
    log.critical("❌ CRASH: SUPABASE_URL is missing.")
    sys.exit(1)
if not SUPABASE_KEY:
    log.critical("❌ CRASH: SUPABASE_KEY is missing.")
    sys.exit(1)
if not KIRKA_API_KEY:
    log.critical("❌ CRASH: KIRKA_API_KEY is missing.")
    sys.exit(1)

log.info("✅ All Environment Variables found.")

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_BASE_URL = "https://api.kirka.io"
API_CACHE      = {}
CACHE_DURATION = 60
API_SEMAPHORE = asyncio.Semaphore(5)

TIER_ORDER      = ["S", "A+", "A", "B", "C", "F"]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}

SCRIM_STATE = {"active": False, "score_a": 0, "score_b": 0}
http_session = None

# ─────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────
def kirka_headers():
    return {"ApiKey": KIRKA_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}

def supabase_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

def supabase_endpoint(path: str) -> str:
    return f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path}"

def get_cached(key):
    data = API_CACHE.get(key)
    if not data: return None
    if time.time() - data["time"] > CACHE_DURATION:
        del API_CACHE[key]
        return None
    return data["value"]

def set_cache(key, value):
    API_CACHE[key] = {"value": value, "time": time.time()}

def to_fancy_font(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    return str(text).translate(str.maketrans(normal, fancy))

def make_embed(title, description="", color=discord.Color.from_rgb(63, 207, 142)):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Made by vlaims • api.kirka.io")
    return embed

# ─────────────────────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────────────────────
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True 
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        global http_session
        log.info("Initializing HTTP Session...")
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        self.background_cache.start()
        log.info("✅ Bot setup complete.")

    async def close(self):
        self.background_cache.cancel()
        global http_session
        if http_session: 
            await http_session.close()
        await super().close()

bot = MyBot()

# ─────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=10)
async def background_cache():
    try:
        if not http_session: return
        async with http_session.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                set_cache("full_roster", data)
    except Exception as e:
        log.error(f"Cache error: {e}")

@background_cache.before_loop
async def before_cache():
    await bot.wait_until_ready()

# ─────────────────────────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────────────────────────
async def kirka_get_profile(short_id: str):
    clean_id = short_id.replace('#', '').strip().upper()
    cache_key = f"profile:{clean_id}"
    cached = get_cached(cache_key)
    if cached: return cached
    
    async with API_SEMAPHORE:
        try:
            if not http_session: return None
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
        except Exception:
            return None

async def get_roster_player_by_name(name: str):
    url = supabase_endpoint(f"roster?name=ilike.{name}&select=*")
    try:
        if not http_session: return None
        async with http_session.get(url, headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
            return None
    except Exception: return None

async def get_roster_player_by_discord(discord_name: str):
    url = supabase_endpoint(f"roster?discord_handle=eq.{discord_name}&select=*")
    try:
        if not http_session: return None
        async with http_session.get(url, headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
            return None
    except Exception: return None

async def update_player_points(name: str, new_points: float):
    url = supabase_endpoint(f"roster?name=eq.{name}")
    try:
        if not http_session: return False
        async with http_session.patch(url, headers=supabase_headers(), json={"points": round(new_points, 2)}) as resp:
            return resp.status in [200, 204]
    except Exception: return False

async def roster_autocomplete(interaction: discord.Interaction, current: str):
    roster = get_cached("full_roster") or []
    suggestions = []
    current_lower = current.lower()
    for player in roster:
        name = player.get("name", "")
        if current_lower in name.lower():
            suggestions.append(app_commands.Choice(name=name, value=name))
    return suggestions[:25]

# ─────────────────────────────────────────────────────────────
# UI VIEWS (Fixed Indentation)
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

class ScrimView(discord.ui.View):
    def __init__(self, clan_a, clan_b, map_name):
        super().__init__(timeout=None)
        self.clan_a = clan_a
        self.clan_b = clan_b
        self.map = map_name
        self.score_a = 0
        self.score_b = 0

    def get_embed(self):
        embed = discord.Embed(title=f"⚔️ LIVE SCRIM: {self.clan_a} vs {self.clan_b}", color=discord.Color.red())
        embed.add_field(name="Map", value=self.map, inline=False)
        embed.add_field(name=self.clan_a, value=str(self.score_a), inline=True)
        embed.add_field(name=self.clan_b, value=str(self.score_b), inline=True)
        return embed

    @discord.ui.button(label=f"{clan_a} +1", style=discord.ButtonStyle.blurple)
    async def add_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.score_a += 1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label=f"{clan_b} +1", style=discord.ButtonStyle.blurple)
    async def add_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.score_b += 1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="End Scrim", style=discord.ButtonStyle.red)
    async def end_scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        winner = self.clan_a if self.score_a > self.score_b else (self.clan_b if self.score_b > self.score_a else "Draw")
        embed = discord.Embed(title="🏁 Scrim Finished", description=f"Winner: **{winner}** ({self.score_a} - {self.score_b})", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=None)

class PollView(discord.ui.View):
    def __init__(self, question):
        super().__init__(timeout=None)
        self.question = question
        self.votes = {"Yes": 0, "No": 0}

    async def update(self, interaction, choice):
        self.votes[choice] += 1
        await interaction.response.edit_message(content=f"**{self.question}**\n👍 Yes: {self.votes['Yes']}\n👎 No: {self.votes['No']}")

    @discord.ui.button(emoji="👍", style=discord.ButtonStyle.green)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "Yes")

    @discord.ui.button(emoji="👎", style=discord.ButtonStyle.red)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "No")

class ChallengeResultView(discord.ui.View):
    def __init__(self, c_data, o_data, bet, c_mem, o_mem):
        super().__init__(timeout=300)
        self.c_data = c_data
        self.o_data = o_data
        self.bet = bet
        self.c_mem = c_mem
        self.o_mem = o_mem
        self.resolved = False

    async def resolve(self, interaction, winner_mem, loser_mem, w_data, l_data):
        if self.resolved: 
            return
        self.resolved = True
        
        payout = round(self.bet * TIER_MULTIPLIER.get(w_data.get("tier", "F").strip(), 1.0), 2)
        
        w_new = float(w_data.get("points", 0)) + payout
        l_new = max(0, float(l_data.get("points", 0)) - self.bet)
        
        await update_player_points(w_data["name"], w_new)
        await update_player_points(l_data["name"], l_new)
        
        embed = discord.Embed(title="⚔️ Challenge Result", color=discord.Color.gold())
        embed.add_field(name="Winner", value=f"{winner_mem.mention} (+{payout})", inline=False)
        embed.add_field(name="Loser", value=f"{loser_mem.mention} (-{self.bet})", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Challenger Won", style=discord.ButtonStyle.green)
    async def c_win(self, i: discord.Interaction, b: discord.ui.Button):
        if not any(r.name == "leader" for r in i.user.roles):
            await i.response.send_message("Leaders only.", ephemeral=True)
            return
        await self.resolve(i, self.c_mem, self.o_mem, self.c_data, self.o_data)

    @discord.ui.button(label="Opponent Won", style=discord.ButtonStyle.blurple)
    async def o_win(self, i: discord.Interaction, b: discord.ui.Button):
        if not any(r.name == "leader" for r in i.user.roles):
            await i.response.send_message("Leaders only.", ephemeral=True)
            return
        await self.resolve(i, self.o_mem, self.c_mem, self.o_data, self.c_data)

class ChallengeAcceptView(discord.ui.View):
    def __init__(self, c_data, o_data, bet, c_mem, o_mem):
        super().__init__(timeout=120)
        self.c_data = c_data
        self.o_data = o_data
        self.bet = bet
        self.c_mem = c_mem
        self.o_mem = o_mem

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.o_mem.id: 
            return
        await i.response.edit_message(view=ChallengeResultView(self.c_data, self.o_data, self.bet, self.c_mem, self.o_mem))

# ─────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="sync", description="Sync commands (Admin Only)")
@app_commands.default_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed: {e}")

@bot.tree.command(name="scrim", description="Start a scrim scoreboard")
@app_commands.describe(opponent="Opponent Clan", map_name="Map being played")
async def scrim(interaction: discord.Interaction, opponent: str, map_name: str):
    SCRIM_STATE["active"] = True
    view = ScrimView("Kiss", opponent, map_name)
    await interaction.response.send_message(embed=view.get_embed(), view=view)

@bot.tree.command(name="members", description="View roster")
async def members(i: discord.Interaction):
    await i.response.defer()
    roster = get_cached("full_roster")
    if not roster:
        async with http_session.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as resp:
            roster = await resp.json() if resp.status == 200 else []
            
    lines = [f"**{p['name']}** | Pts: {p.get('points',0)}" for p in roster]
    pages = ["\n".join(lines[j:j+10]) for j in range(0, len(lines), 10)]
    
    view = PaginationView(pages, "Kiss Clan Roster")
    await i.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="profile", description="Kirka Profile")
@app_commands.autocomplete(player_id=roster_autocomplete)
async def profile(i: discord.Interaction, player_id: str):
    await i.response.defer()
    data = await kirka_get_profile(player_id)
    if not data: 
        await i.followup.send("Not found")
        return
    
    stats = data.get('stats', {})
    kd = round(stats.get('kills',0)/max(stats.get('deaths',1),1),2)
    embed = discord.Embed(title=data.get('name'), description=f"#{data.get('shortId')}", color=discord.Color.green())
    embed.add_field(name="KD", value=kd)
    embed.add_field(name="PRP", value=data.get('klo2V2',0))
    await i.followup.send(embed=embed)

@bot.tree.command(name="playercard", description="Generate a profile image")
@app_commands.autocomplete(name=roster_autocomplete)
async def playercard(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        await interaction.followup.send("❌ Pillow library not installed.", ephemeral=True)
        return
        
    player = await get_roster_player_by_name(name)
    if not player:
        await interaction.followup.send("Player not found", ephemeral=True)
        return
        
    profile = await kirka_get_profile(player['player_id'])
    width, height = 500, 250
    img = Image.new('RGB', (width, height), color=(20, 20, 25))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()

    d.rectangle([(10,10), (490, 240)], outline=(63, 207, 142), width=3)
    d.text((30, 30), f"NAME: {player['name'].upper()}", fill=(255, 255, 255), font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    file = discord.File(buffer, filename="card.png")
    await interaction.followup.send(file=file)

@bot.tree.command(name="challenge", description="Challenge a player")
@app_commands.describe(opponent="The opponent", bet="Points to bet")
async def challenge(i: discord.Interaction, opponent: discord.Member, bet: float):
    await i.response.defer()
    if bet <= 0: 
        await i.followup.send("Invalid bet", ephemeral=True)
        return
    
    c_data = await get_roster_player_by_discord(i.user.name)
    o_data = await get_roster_player_by_discord(opponent.name)
    
    if not c_data or not o_data: 
        await i.followup.send("Roster lookup failed.", ephemeral=True)
        return
    if float(c_data.get('points',0)) < bet or float(o_data.get('points',0)) < bet:
        await i.followup.send("Someone is too broke.", ephemeral=True)
        return

    view = ChallengeAcceptView(c_data, o_data, bet, i.user, opponent)
    await i.followup.send(f"⚔️ {i.user.mention} vs {opponent.mention} for `{bet}` pts", view=view)

# ─────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f"🚀 Logged in as {bot.user}")

@bot.event
async def on_connect():
    log.info("📡 Connected to Discord Gateway")

@bot.tree.error
async def on_command_error(i: discord.Interaction, e):
    log.error(f"Command Error: {e}")
    if i.response.is_done():
        if not i.is_done(): 
            await i.followup.send(f"Error: {e}", ephemeral=True)
    else:
        await i.response.send_message(f"Error: {e}", ephemeral=True)

if __name__ == "__main__":
    try:
        bot.run(os.environ.get('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        log.info("Shutting down...")
    except Exception as e:
        log.critical(f"Fatal Error: {e}")