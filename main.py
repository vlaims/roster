import os
import sys
import discord
from discord import app_commands
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import random
import logging
from datetime import datetime, timedelta, time
from discord.enums import ButtonStyle
import json

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"
SUPABASE_URL   = os.environ.get('SUPABASE_URL')
SUPABASE_KEY   = os.environ.get('SUPABASE_KEY')
LOGS_CHANNEL_ID = int(os.environ.get('LOGS_CHANNEL_ID', 0)) 

TIER_ORDER      = ["S", "A+", "A", "B", "C", ""]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}
XP_RATE         = 10 
LEVEL_UP_XP     = 1000
DAILY_REWARD    = 500  # Increased for clan XP
WEEKLY_RESET_DAY = 0 

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def kirka_headers():
    return {"ApiKey": KIRKA_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}

def supabase_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

def supabase_endpoint(path: str) -> str:
    return f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path}"

# ─────────────────────────────────────────────────────────────
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
    except Exception: return None

async def update_roster_member(name: str, data: dict):
    url = supabase_endpoint(f"roster?name=eq.{name}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=supabase_headers(), json=data) as resp:
                return resp.status in [200, 204]
    except Exception: return False

async def log_action(action, user, details):
    # Log to DB (if table exists)
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(supabase_endpoint("logs"), headers=supabase_headers(), json={"action": action, "user_name": user, "details": details})
    except: pass
    # Log to Discord
    if LOGS_CHANNEL_ID:
        try:
            channel = bot.get_channel(LOGS_CHANNEL_ID)
            if channel: await channel.send(f"📝 **{action}** | `{user}`: {details}")
        except: pass

async def add_xp(name, amount, reason="Activity"):
    m = await get_roster_member(name)
    if m:
        new_xp = m.get('xp', 0) + amount
        new_lvl = int(new_xp / LEVEL_UP_XP) + 1
        await update_roster_member(name, {"xp": new_xp, "level": new_lvl})
        # Clan XP Logic
        clan_xp_gain = int(amount / 2)
        # In a real app, we'd have a separate `clans` table.
        # For now, we just log it or increment a global clan score counter.
        log_action("XP", name, f"+{amount} XP. Level Up? {new_lvl > m.get('level', 1)}")

async def add_points(name, amount, reason):
    m = await get_roster_member(name)
    if m:
        new_bal = m.get('points',0)+amount
        await update_roster_member(name, {"points": new_bal})
        await log_action("ECONOMY", name, f"{amount:+} pts ({reason}). New: {new_bal}")

async def add_excuse(user):
    m = await get_roster_member(user)
    if m:
        await update_roster_member(user, {"excuses": m.get('excuses', 0) + 1})

async def add_glaze(user):
    m = await get_roster_member(user)
    if m:
        await update_roster_member(user, {"glaze": m.get('glaze', 0) + 1})

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
# BOT CLASS (With Intents for VC Tracking)
# ─────────────────────────────────────────────────────────────
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True # <--- NEEDED FOR VC TRACKING
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)
        self.daily_leaderboard_task.start()
        self.auto_sync_stats.start()
        self.weekly_reset_check.start()
        self.dynamic_banner_task.start() # <--- NEW TASK
        self.birthday_checker.start()
        print("Bot Ready.")

    # ─────────────────────────────────────────────────────────────
    # BACKGROUND TASKS
    # ─────────────────────────────────────────────────────────────
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

    @tasks.loop(minutes=30) # Check every 30 mins
    async def dynamic_banner_task(self):
        """Updates Guild Banner based on CW Rank."""
        try:
            clan_data = await kirka_get_clan("kiss")
            if clan_data:
                current_rank = clan_data.get('currentClanPosition', 0)
                
                # Define Banner URLs based on Rank
                banners = {
                    1: "https://i.imgur.com/1.png", # Rank 1 Banner
                    2: "https://i.imgur.com/2.png", # Rank 2 Banner
                    3: "https://i.imgur.com/3.png", # Rank 3 Banner
                }
                url = banners.get(current_rank, "https://discord.com/assets/1234.png") # Default

                # Update Server Banner (Requires Manage Server Permission)
                if interaction.guild:
                    try:
                        await interaction.guild.edit(banner=url)
                        print(f"Updated banner to Rank {current_rank}")
                except:
                    pass
        except Exception as e:
            print(f"Dynamic Banner Error: {e}")

    @tasks.loop(time=time(hour=0, minute=0)) # Midnight
    async def birthday_checker(self):
        """Checks for birthdays."""
        roster = get_cached("full_roster")
        if not roster:
            async with aiohttp.ClientSession() as s:
                async with s.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as resp:
                    if resp.status == 200:
                        roster = await resp.json()
            # In a real app, you'd check 'dob' column. Here we mock it for recent joins.
            pass

    @dynamic_banner_task.before_loop
    async def before_banner(self):
        await self.wait_until_ready()

    @birthday_checker.before_loop
    async def before_birthday(self):
        await self.wait_until_ready()

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
        await i.response.send_message(f"📦 You got: {random.choice(['1000 pts', 'Custom Role', 'Nothing', '1 Week Boost'])}!")
    
    @discord.ui.button(label="📦 Legendary (20000 pts)", style=discord.ButtonStyle.gold)
    async def open_legendary(self, i, b):
        await i.response.send_message(f"📦 You got: {random.choice(['20000 pts', 'Custom Nickname', 'VIP Role', 'Clan Role'])}!")

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

class ScrimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.score_a = 0
        self.score_b = 0
    
    @discord.ui.button(label="Team A +1", style=discord.ButtonStyle.blurple)
    async def score_a(self, i, b):
        self.score_a += 1
        await i.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Team B +1", style=discord.ButtonStyle.blurple)
    async def score_b(self, i, b):
        self.score_b += 1
        await i.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="End Scrim", style=discord.ButtonStyle.red)
    async def end_scrim(self, i, b):
        await i.response.edit_message(content="🏁 Scrim Finished.", embed=None, view=None)

    def get_embed(self):
        return discord.Embed(title="⚔️ Live Scrim", color=discord.Color.red()).add_field(name="Team A", value=self.score_a).add_field(name="Team B", value=self.score_b)

class TicketView(discord.ui.Modal):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel
        self.votes = {"Yes": 0, "No": 0}

    @discord.ui.button(label="End Voting")
    async def end_voting(self, i, b):
        winner = "Yes" if self.votes["Yes"] > self.votes["No"] else "No"
        await i.response.edit_message(content=f"🗳️ Voting ended. Winner: **{winner}**", embed=None, view=None)

    @discord.ui.button(emoji="👍", style=discord.ButtonStyle.green)
    async def yes_vote(self, i, b):
        self.votes["Yes"] += 1
        await i.response.edit_message(content=f"👍 Yes: {self.votes['Yes']}\n👎 No: {self.votes['No']}", view=self)

    @discord.ui.button(emoji="👎", style=discord.ui.Button.red)
    async def no_vote(self, i, b):
        self.votes["No"] += 1
        await i.response.edit_message(content=f"👍 Yes: {self.votes['Yes']}\n👎 No: {self.votes['No']}", view=self)

# ─────────────────────────────────────────────────────────────
# COMMANDS (THE BIG LIST)
# ─────────────────────────────────────────────────────────────

# 1. 📊 ANALYTICS
@bot.tree.command(name="dashboard", description="View Clan Dashboard")
async def dashboard(i: discord.Interaction):
    # Mock data
    await i.response.defer()
    stats = f"""
    📊 **Kiss Clan Dashboard**
    ━─────────────────────
    💰 Clan Bank: 15,000,000 Coins
    ┃────👑 Members: 52
    ┃────🏆 CW Rank: #4 (↑ 1 today!)
    └────⚔ Morale: High
    
    📈 This Week's Top Grinder: Vlaims (+500 PRP)
    📉 Least Active: Recruit #22
    """
    await i.followup.send(f"```css\n{stats}\n```")

# 2. 👥 COMMUNITY
@bot.tree.command(name="familytree", description="View Clan Hierarchy")
async def familytree(i: discord.Interaction):
    await i.response.defer()
    roster = get_cached("full_roster")
    if not roster:
        return await i.followup.send("Roster is empty.", ephemeral=True)
    
    # Logic: Sort by 'joined_at' (assuming column exists, else mock it by ID)
    # Since we can't add columns on the fly, we'll assume a static list or sorted by ID for now
    roster.sort(key=lambda x: x.get('name', '').lower())
    
    # Mock Hierarchy
    lines = []
    # If you add a 'role' column to roster (Leader, Co-Leader, Member)
    
    leader = discord.utils.get(i.guild.roles, name="Leader")
    co_leaders = [m for m in roster if any(r.name in [r.name for r in m.get('roles', [])])]
    members = [m for m in roster if m not any(r.name in [r.name for r in co_leaders])]
    
    lines.append(f"👑 **Leader**: {leader.mention if leader else 'Unknown'}")
    for cl in co_leaders:
        lines.append(f"┣── 🛡 **Co-Leader**: {cl.mention}")
        # Find members where cl is in their roles (requires strict role matching or custom logic)
        members_of_cl = [m for m in members if cl in m.get('roles', [])]
        for mem in members_of_cl:
            lines.append(f"    └── 👤 **{mem.name}**")
            
    for mem in members:
        lines.append(f"└── 👤 **{mem.name}**")

    pages = ["\n".join(lines[i:i+5]) for i in range(0, len(lines), 5)]
    view = PaginationView(pages, "🌳 Clan Family Tree")
    await i.followup.send(embed=view.create_embed(), view=view)

@bot.tree.command(name="og", description="Check OG status")
async def og(i: discord.Interaction):
    await i.response.defer()
    m = await get_roster_member(i.user.name)
    if not m:
        return await i.followup.send("You are not in the roster.", ephemeral=True)
    
    is_og = m.get('og_status') == 'OG' or m.get('id', 0) < 10000 # Mock ID check
    await i.followup.send(f"🏆 **OG Status:** {'✅ True' if is_og else 'False'}")

@bot.tree.command(name="quotes", description="Add a funny clan quote")
@app_commands.describe(quote="The quote")
async def quotes(i: discord.Interaction, quote: str):
    await i.response.send_message(f"💬 Saved quote: \"{quote}\"")

@bot.tree.command(name="memories", description="View clan memories")
async def memories(i: discord.Command(interaction):
    # Fetch from memories table (Mocked here)
    mems = ["Vlaims carried the 2v2", "Pengu sat on snake for 5 hours", "Castiels inventory items are fraud."]
    await i.followup.send(f"🗃️ **Clan Memories:**\n\n{chr(10).join([f"- {m}" for m in mems])}")

# 3. 🎨 AESTHETIC & IDENTITY
@bot.tree.command(name="motto", description="Set your clan motto")
async def motto(i: discord.Interaction, motto: str):
    await update_roster_member(i.user.name, {"motd": motto})
    await i.response.send_message(f"✅ Motto updated to: \"{motto}\"")

@bot.treecommand(name="nickname_history", description="View past nicknames")
async def nickname_history(i: discord.Interaction):
    m = await get_roster(i.user.name)
    if m and m.get('nickname_history'):
        hist = "\n".join([f"{idx+1}. {h}" for idx, h in m.get('nickname_history', [])])
        await i.response.send_message(f"📝 **{i.user.display_name}'s Nicknames:**\n{hist}")
    else:
        await i.response.send_message("No history found.")

@bot.tree.command(name="introduce", description="Create a profile")
async def introduce(i: discord.Interaction):
    # In a real app, this opens a Modal. Here's a text version.
    await i.response.send_message("📝 **Introduction Mode**.\nSend your info in the chat (e.g. /info Age: 19, Main: AR")
    # You would set up a listener for `info Age: ...` in `on_message`
    await i.response.send_message("Ready for your intro (Simulated).")

@bot.tree.command(name="bestfriend", description="Show your best friend in the clan")
async def bestfriend(i: discord.Interaction):
    # Logic: Analyze interactions in the logs (simplified)
    # In a real app, you'd query a 'interactions' table.
    await i.response.send_message(f"💑 **Best Friend:** {i.user.mention} is {random.choice(['Vlaims', 'You', 'Pengu', 'Pengu'])}")

# 4. 🧃 ACTIVITY & VC TRACKING
@bot.tree.command(name="checkin", description="Daily Check-in")
async def checkin(i: discord.Interaction):
    await i.response.defer()
    m = await get_roster_member(i.user.name)
    if not m: return await i.response.send_message("Not in roster.", ephemeral=True)
    
    last_checkin = m.get('last_checkin')
    today = datetime.now().date()
    
    if last_checkin and last_checkin != today:
        # Reset streak if missed a day
        await update_roster_member(i.user.name, {"streak": 0})
    
    # Update checkin
    await update_roster_member(i.user.name, {"last_checkin": today})
    
    current_streak = m.get('streak', 0) + 1
    await add_points(i.user.name, 50, "Check-in")
    await add_xp(i.user.name, 100)
    
    await i.followup.send(f"✅ Checked in! (Streak: `{current_streak}` 🔥)")

@bot.tree.command(name="vc_tracker", description="Current VC Status")
async def vc_tracker(i: discord.Icon):
    vc_state = "🟢 **VC Status:** Offline"
    active_channels = [ch for ch in bot.guild.voice_channels if ch.members]
    
    if active_channels:
        members = [m.mention for ch in active_channels for m in ch.members]
        vc_state = f"🎙️ **Active VC:** `{len(active_channels)}` channels."
        vc_state += f"\n👥 Online: {', '.join(members[:10])}"
    else:
        vc_state = "😴 **VC Status:** Offline"
        
    await i.response.send_message(vc_state)

@bot.tree.command(name="nightowl", description="Show late night crew")
async def nightowl(i: discord.Interaction):
    # In a real app, track last message time or VC join time
    await i.response.send_message("🦉 **Night Owls:** Vlaims (Sleeps at 4 AM), Youn (Sleeps at 5 AM)")

# 5. 🤣 FUN & MEMES
@bot.tree.command(name="ship", description="Check duo compatibility")
async def ship(i: discord.Interaction, other: discord.Member):
    # Mock logic: match weapon or winrate
    await i.response.send_message(f"⚓ {i.user.mention} & {other.mention}: {random.choice(['Match Made in Heaven', 'Disaster Waiting to Happen'])}")

@bot.tree.command(name="duo", description="Random Duo")
async def duo(i: discord.Interaction):
    online = [m for m in i.guild.members if not m.bot and m.status == discord.Status.online]
    if len(online) < 2:
        return await i.response.send_message("Need at least 2 people online to start a duo.")
    
    p1, p2 = random.sample(online, 2)
    await i.response.send_message(f"🤝 Today's Duo: {p1.mention} + " & p2.mention})

@bot.tree.command(name="totd", description="Target of the day")
async def totd(i: discord.Interaction):
    await i.response.send_message(f"🎯 **Target of the Day:** {random.choice(i.guild.members).mention}\n**Reason:** {random.choice(['Aimbotting', 'No Grass Touching', 'Grinding'])}")

@bot.tree.command(name="clown", description="Show the biggest clown")
async def clown(i: discord.Interaction):
    # Update DB to track "clown" stat
    m = await get_roster_member(i.user.name)
    
    # If we had a 'clown' column:
    # await update_roster_member(name, {"clown": m.get('clown', 0) + 1})
    
    # Get top clowns
    # ... (DB Query here) ...
    await i.response.send_message("🤡 **Clown Leader:** Vlaims (Reason: Always thinks they are better than they are)")

@bot.tree.command(name="washed", description="Check your 'Glaze' level")
async def washed(i: discord.Interaction):
    m = await get_roster(i.user.name)
    # Mock glaze level based on matches lost
    await i.response.send_message(f"💧 **Glaze Level:** {m.get('glaze', 0)}%")

@bot.tree.command(name="ego")
async def ego(i: discord.ChatInteraction):
    # Check for 'trash talk' in logs
    await i.response.send_message("💅 **Ego:** Your ego is massive.")

# 6. LORE & RIVALRY
@bot.tree.command(name="clanlore", description="View clan history")
async def clanlore(i: discord.Interaction):
    lines = [
        "2023-05-10: Kiss Founded by Vlaims.",
        "2023-06-01: Vlaims touched grass for the first time.",
        "2023-08-15: Kiss defeated VOID in a CW."
        "2023-10-31: Vlaims got 1m points.",
        "Legendary Moment: Pengu clutched the 1v1."
    ]
    pages = ["\n".join(lines[i:i+3] for i in range(0, len(lines), 3)]
    view = PaginationView(pages, "📜 Kiss Lore", "Legendary Moments")
    await i.response.send_message(embed=view.create_embed(), view=view)

@bot.tree.command(name="rivals", description="Track stats against rival clans")
async def rivals(i: discord.Interaction):
    rivals = ["VOID", "GODMODE", "NO GRASS", "SINISTER"]
    stats = {}
    for r in rivals:
        c = await kirka_get_clan(r)
        if c:
            stats[r] = c.get('monthScores', 0)
    
    desc = "\n".join([f"**{r}**: {stats[r]}" for r in stats])
    await i.followup.send(embed=discord.Embed(title="🏆 Rivals", description=desc))

@bot.tree.command(name="newspaper", description="Weekly clan newspaper")
async def newpaper(i: discord.Interaction):
    # Mock content
    headlines = [
        "📰 **Drama Alert**: Vlaims was caught selling passwords!",
        "🏆 **Scrim Win**: Kiss vs VOID (3-1).",
        "🤣 **Grinder of the Week**: Recruit #22 (1,000 kills)"
    ]
    await i.response.send_message("📰 **Clan Newspaper**\n" + "\n".join(headlines))

# 7. 👥 COMMUNITY ECONOMY
@bot.tree.command(name="earn", description="Earn Clan Coins")
async def earn(i: discord.Interaction):
    # Logic: check random event
    await i.response.send_message(f"🎁 **Event Triggered!**\nYou got `500` clan XP and `200` coins!")

@bot.tree.command(name="spend", description="Spend clan coins")
@app_commands.describe(item="Custom Nickname (1000 coins)", role="Custom Nickname")
async def spend(i: discord.Interaction, item: str, role: str):
    # Check balance, deduct, assign role
    await i.response.send_message(f"💸 You purchased **{role}** for 1000 coins (Mock).")

@bot.tree.command(name="gamble", description="Gamble clan coins")
@app_commands.describe(amount="Amount to bet")
async def gamble(i: discord.Interaction, amount: int):
    await i.response.defer()
    # Logic for coinflip
    await i.followup.send_message(f"🪙 Coin Flip... Heads vs Tails...")

# 8. 🌌 DYNAMIC WELCOME & ANNOUNCEMENTS
# This is handled via on_member and tasks.

# ─────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_member(member):
    # Send animated welcome message
    welcome_msg = (
        f"Welcome {member.mention} to Kiss Clan! 🌿\n"
        f"Check your intro with `/introduce`.\n"
        f"Check your status with `/status`."
    await member.send(welcome_msg)

@bot.event
async def on_message(msg):
    if not msg.author.bot and random.random() < 0.05: 
        # Activity XP Logic (Small reward for talking)
        await add_xp(msg.author.name, 5)
    if msg.content.startswith('!'): await bot.process_commands(msg)

# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
bot.run(os.environ.get('DISCORD_TOKEN'))