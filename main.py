import os
import sys
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import random
import logging
from discord.enums import ButtonStyle  # <--- FIXED IMPORT

# ─────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────
from datetime import datetime, timedelta, time

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"
SUPABASE_URL   = os.environ.get('SUPABASE_URL')
SUPABASE_KEY   = os.environ.get('SUPABASE_KEY')
LOGS_CHANNEL_ID = int(os.environ.get('LOGS_CHANNEL_ID', 0)) 

TIER_ORDER      = ["S", "A+", "A", "B", "C", "F"]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}
XP_RATE         = 10 
LEVEL_UP_XP     = 1000
DAILY_REWARD    = 50
WEEKLY_RESET_DAY = 0 

ACTIVE_EVENTS = {}
ACTIVE_CHALLENGES = {}
MATCHMAKING = []

# ─────────────────────────────────────────────────────────────
# AI & CALCULATION HELPERS
# ─────────────────────────────────────────────────────────────
def calculate_team_balance(members_list: list):
    sorted_members = sorted(members_list, key=lambda x: x.get('prp', 0), reverse=True)
    team_a, team_b, score_a, score_b = [], [], 0, 0
    for m in sorted_members:
        if score_a <= score_b:
            team_a.append(m); score_a += m.get('prp', 0)
        else:
            team_b.append(m); score_b += m.get('prp', 0)
    return {"team_a": team_a, "team_b": team_b, "diff": abs(score_a - score_b)}

def ai_predict_stat(current: float, metric: str):
    return current * 1.05 if metric == "growth" else current + random.randint(50, 200)

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
    except Exception: pass
    return None

async def update_roster_member(name: str, data: dict):
    url = supabase_endpoint(f"roster?name=eq.{name}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=supabase_headers(), json=data) as resp:
                return resp.status in [200, 204]
    except Exception: pass
    return False

async def log_action(action, user, details):
    url = supabase_endpoint("logs")
    payload = {"action": action, "user_name": user, "details": details}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, headers=supabase_headers(), json=payload)
    except: pass
    if LOGS_CHANNEL_ID:
        try:
            channel = bot.get_channel(LOGS_CHANNEL_ID)
            if channel: await channel.send(f"📝 **{action}** | `{user}`: {details}")
        except: pass

async def add_xp(name, amount):
    m = await get_roster_member(name)
    if m:
        await update_roster_member(name, {"xp": m.get('xp',0)+amount, "level": int((m.get('xp',0)+amount)/1000)+1})

async def add_points(name, amount, reason):
    m = await get_roster_member(name)
    if m:
        new_bal = m.get('points',0)+amount
        await update_roster_member(name, {"points": new_bal})
        await log_action("ECONOMY", name, f"{amount:+} pts ({reason}). New: {new_bal}")

# ─────────────────────────────────────────────────────────────
# KIRKA API HELPERS
# ─────────────────────────────────────────────────────────────
async def kirka_get_profile(short_id: str):
    clean_id = short_id.replace('#', '').strip()
    if not clean_id: return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{KIRKA_BASE_URL}/api/user/getProfile", headers=kirka_headers(), json={"id": clean_id, "isShortId": True}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 201: return await resp.json()
    except Exception: pass
    return None

async def kirka_get_clan(clan_name: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{KIRKA_BASE_URL}/api/clan/{clan_name}", headers=kirka_headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200: return await resp.json()
    except Exception: pass
    return None

# ─────────────────────────────────────────────────────────────
# BOT CLASS
# ─────────────────────────────────────────────────────────────
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)
        self.daily_leaderboard_task.start()
        self.auto_sync_stats.start()
        self.weekly_reset_check.start()
        print("Bot Ready.")

    @tasks.loop(hours=1)
    async def weekly_reset_check(self):
        if datetime.now().weekday() == WEEKLY_RESET_DAY and datetime.now().hour == 0:
            await log_action("SYSTEM", "Bot", "Weekly Reset.")

    @tasks.loop(time=time(hour=9, minute=0))
    async def daily_leaderboard_task(self):
        if LOGS_CHANNEL_ID:
            channel = self.get_channel(LOGS_CHANNEL_ID)
            if channel: await channel.send("📊 **Daily Leaderboard Reset!**")

    @tasks.loop(minutes=10)
    async def auto_sync_stats(self):
        pass

bot = MyBot()

# ─────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────
class PaginationView(discord.ui.View):
    def __init__(self, pages, title, total_label=""):
        super().__init__(timeout=180)
        self.pages = pages; self.title = title; self.total_label = total_label
        self.current_page = 0
        self.prev_btn.disabled = True
        if len(self.pages) <= 1: self.next_btn.disabled = True

    def create_embed(self):
        desc = (f"### {self.total_label}\n\n" if self.total_label else "") + self.pages[self.current_page]
        return discord.Embed(title=self.title, description=desc, color=discord.Color.from_rgb(63, 207, 142)).set_footer(text=f"Page {self.current_page+1}/{len(self.pages)}")

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

class ChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, bet):
        super().__init__(timeout=300)
        self.challenger = challenger; self.opponent = opponent; self.bet = bet
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i, b):
        if i.user.id != self.opponent.id: return
        await i.response.send_message(f"⚔️ Accepted! {self.challenger.mention} vs {self.opponent.mention}.")
        self.stop()

class PollView(discord.ui.View):
    def __init__(self, question):
        super().__init__(timeout=None)
        self.question = question
        self.votes = {"Yes": 0, "No": 0}

    async def update(self, i, choice):
        self.votes[choice] += 1
        await i.response.edit_message(content=f"**{self.question}**\n👍 Yes: {self.votes['Yes']}\n👎 No: {self.votes['No']}")

    @discord.ui.button(emoji="👍", style=discord.ButtonStyle.green)
    async def yes(self, i, b):
        await self.update(i, "Yes")
        
    @discord.ui.button(emoji="👎", style=discord.ButtonStyle.red)
    async def no(self, i, b):
        await self.update(i, "No")

class ApplicationApprovalView(discord.ui.View):
    def __init__(self, name, player_id, discord_handle):
        super().__init__(timeout=None)
        self.name, self.player_id, self.discord_handle = name, player_id, discord_handle
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_btn")
    async def approve(self, i, b):
        await i.response.defer()
        payload = {"name": self.name, "discord_handle": self.discord_handle, "player_id": self.player_id, "points": 0, "elo": 1200}
        async with aiohttp.ClientSession() as s:
            async with s.post(supabase_endpoint("roster"), headers=supabase_headers(), json=payload) as resp:
                if resp.status in [200, 201]:
                    e = discord.Embed(title="Application Approved", color=discord.Color.green()).add_field(name="Name", value=f"`{self.name}`").add_field(name="Kirka ID", value=f"`{self.player_id}`").add_field(name="Approved by", value=i.user.mention)
                    if i.guild:
                        m = discord.utils.get(i.guild.members, name=self.discord_handle)
                        if m:
                            if k:=discord.utils.get(i.guild.roles, name="kiss"): await m.add_roles(k)
                            if a:=discord.utils.get(i.guild.roles, name="applicator"): await m.remove_roles(a)
                    await i.edit_original_response(embed=e, view=None)
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_btn")
    async def decline(self, i, b):
        await i.response.defer()
        e = discord.Embed(title="Application Declined", color=discord.Color.red()).add_field(name="Name", value=f"`{self.name}`")
        if i.guild:
            m = discord.utils.get(i.guild.members, name=self.discord_handle)
            if m:
                if d:=discord.utils.get(i.guild.roles, name="declined"): await m.add_roles(d)
                if a:=discord.utils.get(i.guild.roles, name="applicator"): await m.remove_roles(a)
        await i.edit_original_response(embed=e, view=None)

class LootboxView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📦 Open (5000 pts)", style=discord.ButtonStyle.blurple)
    async def open_box(self, i, b):
        await i.response.send_message(f"📦 You got: {random.choice(['10000 pts', 'Nothing', 'VIP Role'])}!")
    
    @discord.ui.button(label="📦 Legendary (2000 pts)", style=discord.ButtonStyle.green)
    async def open_legendary(self, i, b):
        await i.response.send_message(f"📦 You got: {random.choice(['10000 pts', 'Custom Nickname', 'Nothing'])}!")

class SnakeDraftView(discord.ui.View):
    def __init__(self, pool, c1, c2):
        super().__init__(timeout=300)
        self.pool = pool
        self.c1 = c1
        self.c2 = c2
        self.turn = c1
        self.team1 = [c1]
        self.team2 = [c2]
        self.update_ui()

    def update_ui(self):
        e = discord.Embed(title="🐍 Snake Draft")
        e.add_field(name="Team 1", value="\n".join([u.mention for u in self.team1]))
        e.add_field(name="Team 2", value="\n".join([u.mention for u in self.team2]))
        e.add_field(name="Pool", value="\n".join([u.mention for u in self.pool]) or "Empty", inline=False)
        self.clear_items()
        if not self.pool:
            self.stop()
            self.embed = discord.Embed(title="🏁 Draft Finished", description=e.description, color=discord.Color.gold())
            return
        for u in self.pool[:5]:
            btn = discord.ui.Button(label=f"Pick {u.display_name}", style=discord.ButtonStyle.green)
            btn.callback = lambda i, u=u: self.pick(i, u)
            self.add_item(btn)
        self.embed = e

    async def pick(self, i, u):
        if i.user.id != self.turn.id:
            return await i.response.send_message("Not your turn", ephemeral=True)
        await i.response.defer()
        if self.turn == self.c1:
            self.team1.append(u); self.turn = self.c2
        else:
            self.team2.append(u); self.turn = self.c1
        self.pool.remove(u)
        await i.edit_original_response(embed=self.embed, view=self)

# ─────────────────────────────────────────────────────────────
# SCOUTING HELPERS
# ─────────────────────────────────────────────────────────────
async def analyze_clan(clan_name):
    data = await kirka_get_clan(clan_name)
    if not data: return None
    m = data.get('members', [])
    if not m: return None
    prps = [x.get('user', {}).get('klo2V2', 0) for x in m if x.get('user', {}).get('klo2V2')]
    kds = [x.get('user', {}).get('stats', {}).get('kills',0)/max(x.get('user', {}).get('stats', {}).get('deaths',1),1) for x in m]
    return {
        "avg_prp": round(sum(prps)/len(prps),2) if prps else 0,
        "strongest": max(m, key=lambda x: x.get('user', {}).get('klo2V2', 0)).get('user', {}).get('name', 'N/A') if m else 'N/A',
        "weakest": min(m, key=lambda x: x.get('user', {}).get('klo2V2', 0)).get('user', {}).get('name', 'N/A') if m else 'N/A'
    }

# ─────────────────────────────────────────────────────────────
# COMMANDS (MERGED)
# ─────────────────────────────────────────────────────────────

# 1. ECONOMY
@bot.tree.command(name="balance")
async def balance(i: discord.Interaction):
    await i.response.defer()
    m = await get_roster_member(i.user.name)
    if m:
        e = discord.Embed(title=f"💰 {i.user.display_name}", color=discord.Color.gold()).add_field(name="Points", value=f"`{m.get('points',0)}`").add_field(name="XP", value=f"`{m.get('xp',0)}`").add_field(name="Streak", value=f"`{m.get('streak',0)}`")
        await i.followup.send(embed=e)
    else: await i.followup.send("Not in roster.", ephemeral=True)

@bot.tree.command(name="daily")
async def daily(i: discord.Interaction):
    await i.response.defer()
    await add_points(i.user.name, DAILY_REWARD, "Daily")
    await i.followup.send(f"✅ Claimed `{DAILY_REWARD}` pts.")

@bot.tree.command(name="shop")
async def shop(i: discord.Interaction):
    await i.response.send_message("🛒 Shop: VIP Role (10k), Boost (5k)", ephemeral=True)

@bot.tree.command(name="lootbox")
async def lootbox(i: discord.Interaction):
    await i.response.send_message("Open a box:", view=LootboxView())

# 2. COMPETITIVE
@bot.tree.command(name="challenge")
@app_commands.describe(opponent="Opponent", bet="Points", mode="1v1")
async def challenge(i: discord.Interaction, opponent: discord.Member, bet: int, mode: str = "1v1"):
    await i.response.defer()
    if opponent.id == i.user.id: return
    await i.followup.send(embed=discord.Embed(title="⚔️ Challenge", description=f"{i.user.mention} vs {opponent.mention} ({mode}) for `{bet}`"), view=ChallengeView(i.user, opponent, bet))

@bot.tree.command(name="record_win")
@app_commands.describe(winner="Winner", loser="Loser")
async def record_win(i: discord.Interaction, winner: str, loser: str):
    await i.response.defer()
    if not any(r.name in ["Leader", "Admin"] for r in i.user.roles): return await i.followup.send("Admins only", ephemeral=True)
    await add_points(winner, 100, "Win"); await add_points(loser, -50, "Loss")
    await i.followup.send(f"✅ Recorded win for {winner}.")

# 3. TOURNAMENT & TEAMS
@bot.tree.command(name="captains")
@app_commands.describe(players="Mention players")
async def captains(i: discord.Interaction, players: str):
    await i.response.defer()
    members = [{"name": p.display_name, "prp": random.randint(1000, 3000)} for p in i.guild.members[:8]]
    teams = calculate_team_balance(members)
    t1 = "\n".join([m['name'] for m in teams['team_a']])
    t2 = "\n".join([m['name'] for m in teams['team_b']])
    await i.followup.send(embed=discord.Embed(title="⚖️ Balanced Teams").add_field(name="Team A", value=t1).add_field(name="Team B", value=t2))

@bot.tree.command(name="draft")
@app_commands.describe(c1="Captain 1", c2="Captain 2")
async def draft(i: discord.Interaction, c1: discord.Member, c2: discord.Member):
    pool = [m for m in i.guild.members if c1.id != m.id and c2.id != m.id][:6]
    view = SnakeDraftView(pool, c1, c2)
    await i.response.send_message(embed=view.embed, view=view)

@bot.tree.command(name="seed")
async def seed(i: discord.Interaction):
    await i.response.defer()
    mock = [f"P{x}" for x in range(1,9)]
    await i.followup.send(embed=discord.Embed(title="🏆 Bracket").add_field(name="QF1", value=f"{mock[0]} vs {mock[7]}").add_field(name="QF2", value=f"{mock[3]} vs {mock[4]}").add_field(name="SF1", value=f"{mock[1]} vs {mock[6]}").add_field(name="SF2", value=f"{mock[2]} vs {mock[5]}"))

# 4. SCOUTING & AI
@bot.tree.command(name="scout")
@app_commands.describe(clan="Clan Name")
async def scout(i: discord.Interaction, clan: str):
    await i.response.defer()
    data = await analyze_clan(clan)
    if data:
        await i.followup.send(embed=discord.Embed(title=f"🕵️ {clan} Analysis").add_field(name="Avg PRP", value=data['avg_prp']).add_field(name="Strongest", value=data['strongest']).add_field(name="Weakest", value=data['weakest']))
    else: await i.followup.send("Clan not found.")

@bot.tree.command(name="mvp")
async def mvp(i: discord.Interaction):
    await i.response.send_message("🌟 (Simulated AI Analysis)\nBased on recent matches, this player has high clutch factor (1vX wins: 15%).")

@bot.tree.command(name="coach")
async def coach(i: discord.Interaction):
    await i.response.send_message("🤖 **AI Advice**: Your positioning on Ghostship is aggressive. Try holding angles more.")

@bot.tree.command(name="touchgrass")
async def touchgrass(i: discord.Interaction):
    await i.response.send_message(f"🌿 Grass Touched: `{random.randint(0,5)}%`.")

@bot.tree.command(name="nolife")
async def nolife(i: discord.Interaction):
    await i.response.send_message(f"😂 No Life Score: `{random.randint(0,100)}`")

@bot.tree.command(name="tierlist")
async def tierlist(i: discord.Interaction):
    await i.response.send_message("📜 **S**: Vlaims\n**A+**: Youn\n**F**: Everyone else")

# 5. DATA & API
@bot.tree.command(name="api_profile")
@app_commands.describe(name="Name")
async def api_profile(i: discord.Interaction, name: str):
    m = await get_roster_member(name)
    json_data = {"name": name, "points": m.get('points',0), "level": m.get('level',1)} if m else {}
    await i.response.send_message(f"```json\n{json_data}\n```")

@bot.tree.command(name="dashboard")
async def dashboard(i: discord.Interaction):
    await i.response.send_message("```[Clan Dashboard]\n[Members: 50]\n[Active: 12]\n[War: #4]\n[Coins: 15M]```")

# 6. ORIGINALS (Members, Register, etc.)
@bot.tree.command(name="members")
async def members(i: discord.Interaction):
    await i.response.defer()
    async with aiohttp.ClientSession() as s:
        async with s.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as r:
            if r.status != 200: return await i.followup.send("DB Error")
            raw = await r.json()
    lines = [f"**{p['name']}** | {p.get('points',0)} pts" for p in raw]
    view = PaginationView(["\n".join(lines[j:j+5]) for j in range(0, len(lines), 5)], "Roster")
    await i.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="register")
@app_commands.describe(name="Name", player_id="ID")
async def register(i: discord.Interaction, name: str, player_id: str):
    await i.response.defer(ephemeral=True)
    lc = discord.utils.get(i.guild.text_channels, name="application-logs")
    await lc.send(content="@smooch", embed=discord.Embed(title="New App", description=f"{i.user.mention}"), view=ApplicationApprovalView(name, player_id, i.user.name))
    await i.followup.send("Sent.")

@bot.tree.command(name="prp")
async def prp(i: discord.Interaction):
    await i.response.defer()
    await i.followup.send("Fetching PRP... (Simulated)")

@bot.tree.command(name="profile")
@app_commands.describe(player_id="ID")
async def profile(i: discord.Interaction, player_id: str):
    await i.response.defer()
    d = await kirka_get_profile(player_id)
    if d:
        e = discord.Embed(title=d.get('name'), description=f"#{d.get('shortId')}")
        e.add_field(name="PRP", value=d.get('klo2V2',0))
        e.add_field(name="K/D", value=d.get('stats',{}).get('kills',0)/max(d.get('stats',{}).get('deaths',1),1))
        await i.followup.send(embed=e)
    else: await i.followup.send("Not found.")

@bot.tree.command(name="claninfo")
async def claninfo(i: discord.Interaction):
    await i.response.defer()
    d = await kirka_get_clan("kiss")
    if d:
        m = d.get('members', [])
        await i.followup.send(embed=discord.Embed(title=f"🏰 Clan KISS").add_field(name="Members", value=len(m)))
    else: await i.followup.send("Not found.")

# ─────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_message(msg):
    if not msg.author.bot and random.random() < 0.1:
        await add_xp(msg.author.name, 10)
    if msg.content.startswith('!'): await bot.process_commands(msg)

# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
bot.run(os.environ.get('DISCORD_TOKEN'))