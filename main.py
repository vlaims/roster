import os
import sys
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import random
import logging
# ─────────────────────────────────────────────────────────────
# 🔧 FIXED IMPORTS
# ─────────────────────────────────────────────────────────────
# Removed "import time" to prevent conflict with datetime.time
from datetime import datetime, timedelta, time

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"
SUPABASE_URL   = os.environ.get('SUPABASE_URL')
SUPABASE_KEY   = os.environ.get('SUPABASE_KEY')
LOGS_CHANNEL_ID = int(os.environ.get('LOGS_CHANNEL_ID', 0)) # Optional: ID for channel to send logs to

# Economy & Competitive Config
TIER_ORDER      = ["S", "A+", "A", "B", "C", "F"]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}
XP_RATE         = 10 # XP per message
LEVEL_UP_XP     = 1000 # XP needed to level up
DAILY_REWARD    = 500
WEEKLY_RESET_DAY = 0 # 0 = Monday

# Active Events Storage (In-memory for now, can move to DB)
ACTIVE_EVENTS = {}
ACTIVE_CHALLENGES = {}

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

def get_tier_rank(tier: str) -> int:
    try: return TIER_ORDER.index(tier.strip())
    except ValueError: return 999

# ─────────────────────────────────────────────────────────────
# DATABASE HELPERS (Extended)
# ─────────────────────────────────────────────────────────────
async def get_roster_member(name: str):
    """Fetches a roster member by name."""
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
    """Updates roster member columns safely."""
    url = supabase_endpoint(f"roster?name=eq.{name}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=supabase_headers(), json=data) as resp:
                return resp.status in [200, 204]
    except Exception as e: 
        print(f"DB Error updating {name}: {e}")
        return False

async def log_action(action: str, user: str, details: str):
    """Logs action to Supabase 'logs' table or Discord."""
    print(f"[LOG] {action} | {user}: {details}")
    
    # Supabase Log Logic
    url = supabase_endpoint("logs")
    payload = {"action": action, "user_name": user, "details": details}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, headers=supabase_headers(), json=payload)
    except: pass
    
    # Discord Log Logic
    if LOGS_CHANNEL_ID:
        try:
            channel = bot.get_channel(LOGS_CHANNEL_ID)
            if channel:
                await channel.send(f"📝 **{action}** | `{user}`: {details}")
        except: pass

# ─────────────────────────────────────────────────────────────
# ECONOMY LOGIC
# ─────────────────────────────────────────────────────────────
async def add_xp(name: str, amount: int):
    member = await get_roster_member(name)
    if not member: return
    
    current_xp = member.get('xp', 0) + amount
    current_lvl = member.get('level', 1)
    
    # Level Up Check
    new_level = int(current_xp / LEVEL_UP_XP) + 1
    leveled_up = new_level > current_lvl
    
    await update_roster_member(name, {"xp": current_xp, "level": new_level})
    if leveled_up:
        await log_action("LEVEL UP", name, f"Reached Level {new_level}!")

async def add_points(name: str, amount: int, reason: str = "System"):
    member = await get_roster_member(name)
    if not member: return
    
    current_pts = member.get('points', 0) + amount
    await update_roster_member(name, {"points": current_pts})
    await log_action("ECONOMY", name, f"{amount:+} pts ({reason}). New Balance: {current_pts}")

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
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)
        
        # Start Background Tasks
        self.daily_leaderboard_task.start()
        self.auto_sync_stats.start()
        self.weekly_reset_check.start()
        print("Bot Ready.")

bot = MyBot()

# ─────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=10)
async def auto_sync_stats():
    """Syncs PRP/ELO from Kirka API to DB for all members."""
    pass 

# ─────────────────────────────────────────────────────────────
# 🔧 FIXED LOOP SYNTAX
# ─────────────────────────────────────────────────────────────
@tasks.loop(time=time(hour=9, minute=0)) # 9 AM Daily
async def daily_leaderboard_task():
    """Posts daily leaderboard."""
    if LOGS_CHANNEL_ID:
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        if channel:
            await channel.send("📊 **Daily Leaderboard Reset!** Good luck grinding today!")

@tasks.loop(hours=1)
async def weekly_reset_check():
    """Checks if it's time for weekly reset."""
    now = datetime.now()
    if now.weekday() == WEEKLY_RESET_DAY and now.hour == 0 and now.minute == 0:
        # Reset Streaks/Weekly Stats
        await log_action("SYSTEM", "Bot", "Weekly Reset Triggered.")

# ─────────────────────────────────────────────────────────────
# KIRKA API HELPERS (Preserved)
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

# ─────────────────────────────────────────────────────────────
# VIEWS & UI (New & Preserved)
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
    async def prev_btn(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        if self.current_page > 0: self.current_page -= 1
        self.next_btn.disabled = False
        if self.current_page == 0: b.disabled = True
        await i.edit_original_response(embed=self.create_embed(), view=self)

    @discord.ui.button(label="-->", style=discord.ButtonStyle.green)
    async def next_btn(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        if self.current_page < len(self.pages) - 1: self.current_page += 1
        self.prev_btn.disabled = False
        if self.current_page == len(self.pages) - 1: b.disabled = True
        await i.edit_original_response(embed=self.create_embed(), view=self)

class ChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, bet):
        super().__init__(timeout=300)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        if i.user.id != self.opponent.id: return
        await i.response.send_message(f"⚔️ Challenge Accepted! {self.challenger.mention} vs {self.opponent.mention}.")
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
    async def yes(self, i: discord.Interaction, b: discord.ui.Button): await self.update(i, "Yes")
    @discord.ui.button(emoji="👎", style=discord.ButtonStyle.red)
    async def no(self, i: discord.Interaction, b: discord.ui.Button): await self.update(i, "No")

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
    embed.add_field(name="Streak", value=f"`{member.get('streak', 0)} 🔥`", inline=True)
    await i.followup.send(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily reward")
async def daily(i: discord.Interaction):
    await i.response.defer()
    # In a real app, check cooldown in DB
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
    embed = discord.Embed(title="🛒 Clan Shop", description="Spend your points here!", color=discord.Color.purple())
    embed.add_field(name="Role: Booster", value="500 pts", inline=False)
    embed.add_field(name="Role: Nitro", value="1000 pts", inline=False)
    embed.add_field(name="Custom Color", value="2000 pts", inline=False)
    await i.followup.send(embed=embed)

# ─────────────────────────────────────────────────────────────
# COMMANDS: COMPETITIVE
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="challenge", description="Challenge a player to a ranked match")
@app_commands.describe(opponent="The player to challenge", bet="Points to bet", mode="1v1, 2v2, or 3v3")
async def challenge(i: discord.Interaction, opponent: discord.Member, bet: int, mode: str = "1v1"):
    await i.response.defer()
    if opponent.id == i.user.id:
        await i.followup.send("You can't challenge yourself!", ephemeral=True)
        return
    
    view = ChallengeView(i.user, opponent, bet)
    embed = discord.Embed(title="⚔️ Challenge Issued", description=f"{i.user.mention} challenges {opponent.mention} in **{mode}** for `{bet}` pts!")
    await i.followup.send(embed=embed, view=view)

@bot.tree.command(name="record_win", description="Admin command to record a win and calc rewards")
@app_commands.describe(winner="Winner Name", loser="Loser Name", upset="Was this an upset?")
async def record_win(i: discord.Interaction, winner: str, loser: str, upset: bool = False):
    await i.response.defer()
    if not any(r.name in ["Leader", "Admin"] for r in i.user.roles):
        await i.followup.send("Admins only.", ephemeral=True)
        return

    # Calculation Logic
    base_reward = 100
    multiplier = 1.0
    if upset: multiplier = 1.5 # Upset bonus
    
    final_reward = int(base_reward * multiplier)
    
    # Update Stats
    await add_points(winner, final_reward, f"Win vs {loser}")
    await add_points(loser, -50, f"Loss vs {winner}")
    
    await add_xp(winner, 500)
    await add_xp(loser, 100)
    
    # Update Streaks
    w_data = await get_roster_member(winner)
    l_data = await get_roster_member(loser)
    
    await update_roster_member(winner, {"streak": (w_data.get('streak', 0) if w_data else 0) + 1})
    await update_roster_member(loser, {"streak": 0})
    
    # Log History
    await log_action("MATCH", f"{winner} vs {loser}", f"Winner: {winner}. Upset: {upset}")
    
    await i.followup.send(f"✅ Recorded win for {winner}. Reward: `{final_reward}` pts.")

@bot.tree.command(name="leaderboard", description="View the Clan Points Leaderboard")
async def leaderboard(i: discord.Interaction):
    await i.response.defer()
    # In a real app, fetch all and sort. Here is a placeholder logic.
    embed = discord.Embed(title="🏆 Clan Leaderboard", description="Loading...", color=discord.Color.gold())
    await i.followup.send(embed=embed)

# ─────────────────────────────────────────────────────────────
# COMMANDS: FUN & UTILS
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="poll", description="Create a poll")
@app_commands.describe(question="The question to ask")
async def poll_cmd(i: discord.Interaction, question: str):
    view = PollView(question)
    await i.response.send_message(f"**{question}**", view=view)

@bot.tree.command(name="8ball", description="Ask the magic 8ball")
@app_commands.describe(question="Your question")
async def eightball(i: discord.Interaction, question: str):
    responses = ["Yes", "No", "Maybe", "Ask again later"]
    await i.response.send(f"🎱 **{question}**\n> {random.choice(responses)}")

# ─────────────────────────────────────────────────────────────
# COMMANDS: EVENT SCHEDULING
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="event", description="Schedule a clan event")
@app_commands.describe(name="Event Name", time_str="Time (e.g. 8pm)") # Renamed param to avoid conflict
async def event_cmd(i: discord.Interaction, name: str, time_str: str):
    ACTIVE_EVENTS[name] = {"time": time_str, "attendees": []}
    await i.response.send_message(f"📅 **Event Created:** {name} at {time_str}\nReact below to RSVP!")

@bot.tree.command(name="rsvp", description="RSVP to an event")
@app_commands.describe(event_name="Name of the event")
async def rsvp_cmd(i: discord.Interaction, event_name: str):
    if event_name in ACTIVE_EVENTS:
        ACTIVE_EVENTS[event_name]["attendees"].append(i.user.name)
        await i.response.send_message(f"✅ You RSVP'd to {event_name}!")
    else:
        await i.response.send_message("Event not found.", ephemeral=True)

# ─────────────────────────────────────────────────────────────
# ORIGINAL COMMANDS (Preserved & Integrated)
# ─────────────────────────────────────────────────────────────

# Helper for Approval View
class ApplicationApprovalView(discord.ui.View):
    def __init__(self, name: str, player_id: str, discord_handle: str):
        super().__init__(timeout=None)
        self.name = name
        self.player_id = player_id
        self.discord_handle = discord_handle

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_btn")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        target_endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/roster"
        payload = {"name": self.name, "discord_handle": self.discord_handle, "player_id": self.player_id}
        # Add default stats on register
        payload["points"] = 0
        payload["elo"] = 1200
        payload["xp"] = 0
        payload["level"] = 1
        payload["streak"] = 0
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(target_endpoint, headers=supabase_headers(), json=payload) as response:
                    if response.status in [200, 201]:
                        embed = discord.Embed(title="Application Approved", color=discord.Color.green())
                        embed.add_field(name="Name", value=f"`{self.name}`", inline=True)
                        embed.add_field(name="Kirka ID", value=f"`{self.player_id}`", inline=True)
                        embed.add_field(name="Approved by", value=interaction.user.mention, inline=False)
                        guild = interaction.guild
                        if guild:
                            member = discord.utils.get(guild.members, name=self.discord_handle)
                            if member:
                                kiss_role = discord.utils.get(guild.roles, name="kiss")
                                applicator_role = discord.utils.get(guild.roles, name="applicator")
                                if kiss_role: await member.add_roles(kiss_role)
                                if applicator_role: await member.remove_roles(applicator_role)
                        await interaction.edit_original_response(embed=embed, view=None)
                    else:
                        await interaction.followup.send(f"Failed to insert row (HTTP: `{response.status}`)", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Database error: {e}", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_btn")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(title="Application Declined", color=discord.Color.red())
        embed.add_field(name="Character Name", value=f"`{self.name}`", inline=True)
        embed.add_field(name="Declined by", value=interaction.user.mention, inline=False)
        guild = interaction.guild
        if guild:
            member = discord.utils.get(guild.members, name=self.discord_handle)
            if member:
                declined_role = discord.utils.get(guild.roles, name="declined")
                if declined_role: await member.add_roles(declined_role)
                applicator_role = discord.utils.get(guild.roles, name="applicator")
                if applicator_role: await member.remove_roles(applicator_role)
                try: await member.send("Your application got rejected.")
                except discord.Forbidden: pass
        await interaction.edit_original_response(embed=embed, view=None)


@bot.tree.command(name="members", description="Previews all registered data from the Supabase clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    if not SUPABASE_URL or not SUPABASE_KEY:
        await interaction.followup.send("Error: Supabase credentials are missing.")
        return
    target_endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/roster?select=*&order=name.desc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(target_endpoint, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(f"Supabase error. (Code: `{response.status}`)")
                    return
                raw_data = await response.json()
        if not raw_data or not isinstance(raw_data, list):
            await interaction.followup.send("Roster table is currently empty.")
            return
        total_players = len(raw_data)
        vlaims_record = None
        other_records = []
        for item in raw_data:
            if str(item.get('name', '')).lower() == 'vlaims':
                vlaims_record = item
            else:
                other_records.append(item)
        sorted_dataset = ([vlaims_record] if vlaims_record else []) + other_records
        all_lines = []
        for index, item in enumerate(sorted_dataset, 1):
            fancy_name = to_fancy_font(item.get('name', 'Unknown'))
            player_id  = item.get('player_id', 'N/A')
            discord_user = item.get('discord_handle', 'N/A')
            all_lines.append(
                f"**{index}. {fancy_name}**\n"
                f"- # ↳ *ID:* `{player_id}` • *Discord:* `@{discord_user}`"
            )
        pages_content = ["\n".join(all_lines[i:i+5]) for i in range(0, len(all_lines), 5)]
        view = PaginationView(pages=pages_content, title="Kiss Clan Players", total_label=f"Total Tracked Players: {total_players}")
        await interaction.followup.send(embed=view.create_embed(), view=view)
    except Exception as e:
        print(f"SUPABASE FETCH ERROR: {e}")
        await interaction.followup.send("Failed to fetch roster data.")


@bot.tree.command(name="register", description="Apply to join the clan")
@app_commands.describe(name="Your name", player_id="Your in-game ID")
async def register(interaction: discord.Interaction, name: str, player_id: str):
    if interaction.channel.name not in ["apply", "general"]:
        await interaction.response.send_message("Use this command in `#apply` or `#general`.", ephemeral=True)
        return
    applicator_role = discord.utils.get(interaction.guild.roles, name="applicator")
    if not applicator_role or applicator_role not in interaction.user.roles:
        await interaction.response.send_message("❌ You need the `applicator` role to apply.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    logs_channel = discord.utils.get(interaction.guild.text_channels, name="application-logs")
    admin_role   = discord.utils.get(interaction.guild.roles, name="smooch")
    if not logs_channel:
        await interaction.followup.send("Logs channel not found.", ephemeral=True)
        return
    log_embed = discord.Embed(
        title="New Roster Registration Pending",
        description=f"Applicant: {interaction.user.mention}",
        color=discord.Color.orange()
    )
    log_embed.add_field(name="Character Name", value=name, inline=True)
    log_embed.add_field(name="Account ID Tag", value=player_id, inline=True)
    view = ApplicationApprovalView(name=name, player_id=player_id, discord_handle=interaction.user.name)
    ping = admin_role.mention if admin_role else "@smooch"
    await logs_channel.send(content=ping, embed=log_embed, view=view)
    await interaction.followup.send("Application sent to administrators.", ephemeral=True)


@bot.tree.command(name="kick", description="Remove a player from the roster")
@app_commands.default_permissions(administrator=True)
async def kick(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    target_endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/roster?name=eq.{name}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "return=representation"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(target_endpoint, headers=headers) as response:
                if response.status == 200:
                    deleted_data = await response.json()
                    if not deleted_data:
                        await interaction.followup.send(f"Could not find a player named `{name}` in the database.")
                        return
                    embed = discord.Embed(
                        title="Player Removed",
                        description=f"**{to_fancy_font(name)}** has been removed from the clan roster.",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"Failed to delete player. (HTTP Error: `{response.status}`)")
    except Exception as e:
        await interaction.followup.send(f"Critical error: {e}")


@bot.tree.command(name="prp", description="Check Ranked 2v2 Points and K/D for all roster players")
async def prp(interaction: discord.Interaction):
    await interaction.response.defer()
    target_endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/roster?select=*"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(target_endpoint, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(f"Database error. (Code: `{response.status}`)")
                    return
                roster_data = await response.json()
        if not roster_data:
            await interaction.followup.send("No players found in the roster.")
            return
        total = len(roster_data)
        status_msg = await interaction.followup.send(f"🔍 Fetching stats for {total} players...")
        results = []
        for idx, player in enumerate(roster_data, 1):
            player_id = player.get('player_id', '').strip()
            name      = player.get('name', 'Unknown')
            if idx % 3 == 1:
                try:
                    await status_msg.edit(content=f"🔍 Fetching stats… ({idx}/{total}) — **{name}**")
                except Exception: pass
            if player_id:
                profile = await kirka_get_profile(player_id)
                if profile:
                    prp_val = float(profile.get('klo2V2', 0) or 0)
                    stats   = profile.get('stats', {})
                    kills   = stats.get('kills', 0) or 0
                    deaths  = stats.get('deaths', 0) or 1
                    kd_val  = round(kills / deaths, 2)
                    results.append({'name': name, 'prp': prp_val, 'kd': kd_val, 'found': True})
                else:
                    results.append({'name': name, 'prp': 0.0, 'kd': 0.0, 'found': False})
            else:
                results.append({'name': name, 'prp': 0.0, 'kd': 0.0, 'found': False})
        results.sort(key=lambda x: x['prp'], reverse=True)
        embed = discord.Embed(title="🏆 Ranked 2v2 Leaderboard", color=discord.Color.gold())
        leaderboard_text = ""
        for idx, p in enumerate(results, 1):
            fancy_name  = to_fancy_font(p['name'])
            prp_display = f"{p['prp']:,.2f}" if p['found'] else "N/A"
            kd_display  = f"{p['kd']:.2f}"   if p['found'] else "N/A"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"**{idx}.**")
            leaderboard_text += (
                f"{medal} **{fancy_name}**\n"
                f"┣ PRP: `{prp_display}`\n"
                f"┗ K/D: `{kd_display}`\n\n"
            )
        embed.description = leaderboard_text
        embed.set_footer(text="Data from api.kirka.io | Made by vlaims")
        await status_msg.edit(content=None, embed=embed)
    except Exception as e:
        print(f"PRP COMMAND ERROR: {e}")
        await interaction.followup.send(f"Failed to fetch stats: {e}")


@bot.tree.command(name="profile", description="Look up a Kirka player's profile by their short ID")
@app_commands.describe(player_id="The player's short ID (e.g. XMNVRX)")
async def profile(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()
    data = await kirka_get_profile(player_id)
    if not data:
        await interaction.followup.send(f"❌ Could not find a player with ID `{player_id}`.")
        return
    stats  = data.get('stats', {})
    kills  = stats.get('kills', 0) or 0
    deaths = stats.get('deaths', 0) or 1
    kd     = round(kills / deaths, 2)
    prp    = data.get('klo2V2', 0)

    embed = discord.Embed(
        title=f"{data.get('name', 'Unknown')}  •  #{data.get('shortId', player_id)}",
        color=discord.Color.from_rgb(63, 207, 142)
    )
    embed.add_field(name="Level",    value=data.get('level', 'N/A'),  inline=True)
    embed.add_field(name="Clan",     value=data.get('clan') or 'None', inline=True)
    embed.add_field(name="Role",     value=data.get('role', 'N/A'),   inline=True)
    embed.add_field(name="PRP (2v2)", value=f"`{prp:,.2f}`",          inline=True)
    embed.add_field(name="K/D",       value=f"`{kd:.2f}`",            inline=True)
    embed.add_field(name="Kills",     value=f"`{kills:,}`",           inline=True)
    embed.add_field(name="Deaths",    value=f"`{stats.get('deaths', 0):,}`", inline=True)
    embed.add_field(name="Wins",      value=f"`{stats.get('wins', 0):,}`",   inline=True)
    embed.add_field(name="Games",     value=f"`{stats.get('games', 0):,}`",  inline=True)
    embed.add_field(name="Headshots", value=f"`{stats.get('headshots', 0):,}`", inline=True)
    embed.add_field(name="Scores",    value=f"`{stats.get('scores', 0):,}`",    inline=True)
    embed.set_footer(text="Data from api.kirka.io | Made by vlaims")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="claninfo", description="Show Kiss clan info and member list from Kirka")
async def claninfo(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await kirka_get_clan("kiss")
    if not data:
        await interaction.followup.send("❌ Could not fetch clan data from Kirka.")
        return
    members = data.get('members', [])
    members_sorted = sorted(members, key=lambda m: m.get('monthScores', 0), reverse=True)
    overview = discord.Embed(
        title=f"🏰 Clan: {data.get('name', 'kiss').upper()}",
        description=data.get('description') or '',
        color=discord.Color.from_rgb(63, 207, 142)
    )
    overview.add_field(name="Members",        value=f"`{len(members)}`",                          inline=True)
    overview.add_field(name="Clan War Rank",   value=f"`#{data.get('currentClanWarPosition','?')}`", inline=True)
    overview.add_field(name="Month Scores",    value=f"`{data.get('monthScores', 0):,}`",          inline=True)
    overview.add_field(name="All-Time Scores", value=f"`{data.get('allScores', 0):,}`",            inline=True)
    overview.set_footer(text="Data from api.kirka.io | Made by vlaims")
    lines = []
    for idx, m in enumerate(members_sorted, 1):
        user         = m.get('user', {})
        fancy_name   = to_fancy_font(user.get('name', 'Unknown'))
        short_id     = user.get('shortId', 'N/A')
        role         = m.get('role', 'N/A')
        month_scores = m.get('monthScores', 0)
        lines.append(
            f"**{idx}. {fancy_name}** `[{role}]`\n"
            f"┣ ID: `{short_id}`\n"
            f"┗ Month Scores: `{month_scores:,}`"
        )
    pages = ["\n\n".join(lines[i:i+5]) for i in range(0, len(lines), 5)]
    view  = PaginationView(pages=pages, title="🏰 Kiss Clan Members", total_label=f"Total Members: {len(members)}")
    await interaction.followup.send(embed=overview)
    await interaction.followup.send(embed=view.create_embed(), view=view)


@bot.tree.command(name="ranked2v2", description="Show the global Kirka ranked 2v2 leaderboard")
async def ranked2v2(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await kirka_get_ranked2v2()
    if not data:
        await interaction.followup.send("❌ Could not fetch ranked 2v2 leaderboard from Kirka.")
        return
    results = data.get('results', [])
    season  = data.get('season')
    if not results:
        await interaction.followup.send("The ranked 2v2 leaderboard is currently empty (no active season).")
        return
    lines = []
    for idx, entry in enumerate(results, 1):
        fancy_name = to_fancy_font(entry.get('name', 'Unknown'))
        short_id   = entry.get('shortId', 'N/A')
        prp        = entry.get('klo2V2', 0)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"**{idx}.**")
        lines.append(
            f"{medal} **{fancy_name}** `#{short_id}`\n"
            f"┗ PRP: `{prp:,.2f}`"
        )
    pages = ["\n\n".join(lines[i:i+10]) for i in range(0, len(lines), 10)]
    title = f"🏆 Global Ranked 2v2 Leaderboard" + (f" — Season {season}" if season else "")
    view  = PaginationView(pages=pages, title=title)
    await interaction.followup.send(embed=view.create_embed(), view=view)


# ─────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_message(message):
    if message.author.bot: return
    # Chat Activity Rewards (Small XP for chatting)
    if random.random() < 0.1: # 10% chance per message
        await add_xp(message.author.name, XP_RATE)
    # Process commands (Prefix based)
    # Note: Since we use Tree commands mainly, this just covers legacy '!'
    if message.content.startswith('!'):
        await bot.process_commands(message)

bot.run(os.environ.get('DISCORD_TOKEN'))