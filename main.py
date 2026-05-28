import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import time
from functools import wraps

# ─────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"
API_CACHE      = {}
CACHE_DURATION = 60  # seconds

# Shop Configuration
SHOP_ITEMS = {
    "booster": {"id": "booster", "name": "XP Booster", "price": 500, "desc": "A temporary role for attention."},
    "custom_color": {"id": "custom_color", "name": "Custom Color", "price": 1000, "desc": "Get a custom colored role."},
    "nitro": {"id": "nitro", "name": "Fake Nitro", "price": 5000, "desc": "A cool role named 'Nitro'"},
    "premium": {"id": "premium", "name": "Premium Status", "price": 10000, "desc": "Top tier role in the server."},
}

# Activity State
ACTIVE_ACTIVITY = {
    "active": False,
    "points": 0,
    "participants": [], # List of discord.Member objects
    "starter": None
}

http_session = None

# Tier order — lower index = higher tier
TIER_ORDER      = ["S", "A+", "A", "B", "C", "F"]
TIER_MULTIPLIER = {"S": 3.0, "A+": 2.5, "A": 2.0, "B": 1.5, "C": 1.0, "F": 0.5}

def tier_rank(tier: str) -> int:
    """Lower number = higher tier. Returns 999 if unknown."""
    try:
        return TIER_ORDER.index(tier.strip())
    except ValueError:
        return 999

def kirka_headers():
    return {
        "ApiKey": KIRKA_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def supabase_headers():
    key = os.environ.get('SUPABASE_KEY')
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def supabase_endpoint(path: str) -> str:
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    return f"{base}/rest/v1/{path}"


# ─────────────────────────────────────────────────────────────
# FANCY FONT
# ─────────────────────────────────────────────────────────────
def to_fancy_font(text):
    normal_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy_chars  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    trans = str.maketrans(normal_chars, fancy_chars)
    return str(text).translate(trans)


# ─────────────────────────────────────────────────────────────
# EMBED HELPER
# ─────────────────────────────────────────────────────────────
def make_embed(title, description="", color=discord.Color.from_rgb(63, 207, 142)):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Made by vlaims • api.kirka.io")
    return embed


# ─────────────────────────────────────────────────────────────
# CACHE HELPERS
# ─────────────────────────────────────────────────────────────
def get_cached(key):
    data = API_CACHE.get(key)
    if not data:
        return None
    if time.time() - data["time"] > CACHE_DURATION:
        del API_CACHE[key]
        return None
    return data["value"]

def set_cache(key, value):
    API_CACHE[key] = {"value": value, "time": time.time()}


# ─────────────────────────────────────────────────────────────
# COOLDOWN DECORATOR
# ─────────────────────────────────────────────────────────────
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
                    await interaction.response.send_message(
                        f"⏳ Slow down. Try again in `{remaining:.1f}s`", ephemeral=True
                    )
                    return
            cooldowns[user_id] = now + seconds
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────────────────────
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True # Good practice to have
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        global http_session
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)
        print(f"✅ Logged in as {self.user}")

    async def close(self):
        global http_session
        if http_session:
            await http_session.close()
        await super().close()


bot = MyBot()


# ─────────────────────────────────────────────────────────────
# KIRKA API HELPERS
# ─────────────────────────────────────────────────────────────
async def kirka_get_profile(short_id: str):
    clean_id = short_id.replace('#', '').strip().upper()
    if not clean_id:
        return None
    cache_key = f"profile:{clean_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached
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
            print(f"[Kirka] Failed profile lookup: {clean_id} → HTTP {resp.status}")
            return None
    except Exception as e:
        print(f"[Kirka] Profile error for {clean_id}: {e}")
        return None


async def kirka_get_clan(clan_name: str):
    try:
        async with http_session.get(
            f"{KIRKA_BASE_URL}/api/clan/{clan_name}",
            headers=kirka_headers()
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[Kirka] getClan {clan_name} → HTTP {resp.status}")
            return None
    except Exception as e:
        print(f"[Kirka] getClan error: {e}")
        return None


async def kirka_get_ranked2v2():
    try:
        async with http_session.get(
            f"{KIRKA_BASE_URL}/api/leaderboard/ranked2V2",
            headers=kirka_headers()
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[Kirka] ranked2V2 → HTTP {resp.status}")
            return None
    except Exception as e:
        print(f"[Kirka] ranked2V2 error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# SUPABASE HELPERS
# ─────────────────────────────────────────────────────────────
async def get_roster_player_by_discord(discord_name: str):
    """Fetch a roster row by discord_handle."""
    url = supabase_endpoint(f"roster?discord_handle=eq.{discord_name}&select=*")
    try:
        async with http_session.get(url, headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
            return None
    except Exception as e:
        print(f"[Supabase] get_roster_player_by_discord error: {e}")
        return None


async def get_roster_player_by_name(name: str):
    """Fetch a roster row by name (case-insensitive)."""
    url = supabase_endpoint(f"roster?name=ilike.{name}&select=*")
    try:
        async with http_session.get(url, headers=supabase_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data[0] if data else None
            return None
    except Exception as e:
        print(f"[Supabase] get_roster_player_by_name error: {e}")
        return None


async def update_player_points(player_name: str, new_points: float):
    """PATCH the points column for a given player name."""
    url = supabase_endpoint(f"roster?name=eq.{player_name}")
    try:
        async with http_session.patch(
            url,
            headers=supabase_headers(),
            json={"points": round(new_points, 2)}
        ) as resp:
            return resp.status in [200, 204]
    except Exception as e:
        print(f"[Supabase] update_player_points error: {e}")
        return False

# ─────────────────────────────────────────────────────────────
# AUTOCOMPLETE HELPER
# ─────────────────────────────────────────────────────────────
async def roster_autocomplete(interaction: discord.Interaction, current: str):
    # Small cache for autocomplete to avoid hitting DB every keystroke
    try:
        async with http_session.get(supabase_endpoint("roster?select=name,player_id&limit=25"), headers=supabase_headers()) as resp:
            roster = await resp.json()
    except:
        roster = []
        
    suggestions = []
    current_lower = current.lower()
    
    for player in roster:
        name = player.get("name", "")
        pid  = player.get("player_id", "")
        if current_lower in name.lower() or current_lower in pid.lower():
            suggestions.append(app_commands.Choice(name=name, value=name))
    
    return suggestions[:25]


# ─────────────────────────────────────────────────────────────
# PAGINATION VIEW
# ─────────────────────────────────────────────────────────────
class PaginationView(discord.ui.View):
    def __init__(self, pages: list, title: str, total_label: str = ""):
        super().__init__(timeout=180)
        self.pages = pages
        self.title = title
        self.total_label = total_label
        self.current_page = 0
        self.prev_btn.disabled = True
        if len(self.pages) <= 1:
            self.next_btn.disabled = True

    def create_embed(self):
        desc = (f"### {self.total_label}\n\n" if self.total_label else "") + self.pages[self.current_page]
        embed = discord.Embed(title=self.title, description=desc, color=discord.Color.from_rgb(63, 207, 142))
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)} | Made by vlaims")
        return embed

    @discord.ui.button(label="<--", style=discord.ButtonStyle.green, custom_id="prev_btn")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
        self.next_btn.disabled = False
        if self.current_page == 0:
            button.disabled = True
        await interaction.edit_original_response(embed=self.create_embed(), view=self)

    @discord.ui.button(label="-->", style=discord.ButtonStyle.green, custom_id="next_btn")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        self.prev_btn.disabled = False
        if self.current_page == len(self.pages) - 1:
            button.disabled = True
        await interaction.edit_original_response(embed=self.create_embed(), view=self)


# ─────────────────────────────────────────────────────────────
# ADMIN APPROVAL BUTTONS
# ─────────────────────────────────────────────────────────────
class ApplicationApprovalView(discord.ui.View):
    def __init__(self, name: str, player_id: str, discord_handle: str):
        super().__init__(timeout=None)
        self.name = name
        self.player_id = player_id
        self.discord_handle = discord_handle

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_btn")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        payload = {
            "name": self.name,
            "discord_handle": self.discord_handle,
            "player_id": self.player_id,
            "points": 0
        }
        try:
            async with http_session.post(
                supabase_endpoint("roster"),
                headers=supabase_headers(),
                json=payload
            ) as response:
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
                            if kiss_role:
                                await member.add_roles(kiss_role)
                            if applicator_role:
                                await member.remove_roles(applicator_role)
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
                if declined_role:
                    await member.add_roles(declined_role)
                applicator_role = discord.utils.get(guild.roles, name="applicator")
                if applicator_role:
                    await member.remove_roles(applicator_role)
                try:
                    await member.send("Your application got rejected your a fucking chud get better 😂😂😂")
                except discord.Forbidden:
                    pass
        await interaction.edit_original_response(embed=embed, view=None)


# ─────────────────────────────────────────────────────────────
# CHALLENGE SYSTEM
# ─────────────────────────────────────────────────────────────

class ChallengeResultView(discord.ui.View):
    def __init__(self, challenger_data: dict, opponent_data: dict, bet: float,
                 challenger_member: discord.Member, opponent_member: discord.Member):
        super().__init__(timeout=300)
        self.challenger_data   = challenger_data
        self.opponent_data     = opponent_data
        self.bet               = bet
        self.challenger_member = challenger_member
        self.opponent_member   = opponent_member
        self.resolved          = False

    def calculate_payout(self, winner_data: dict, loser_data: dict) -> float:
        winner_tier_rank = tier_rank(winner_data.get("tier", "F"))
        loser_tier_rank  = tier_rank(loser_data.get("tier", "F"))
        if winner_tier_rank > loser_tier_rank:
            multiplier = TIER_MULTIPLIER.get(winner_data.get("tier", "F").strip(), 1.0)
            return round(self.bet * multiplier, 2)
        else:
            return round(self.bet, 2)

    async def resolve(self, interaction: discord.Interaction, winner_member: discord.Member, loser_member: discord.Member,
                      winner_data: dict, loser_data: dict):
        if self.resolved:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        self.resolved = True

        payout      = self.calculate_payout(winner_data, loser_data)
        winner_tier = winner_data.get("tier", "?")
        loser_tier  = loser_data.get("tier", "?")
        is_upset    = tier_rank(winner_tier) > tier_rank(loser_tier)
        multiplier  = TIER_MULTIPLIER.get(winner_tier.strip(), 1.0) if is_upset else 1.0

        winner_current_pts = float(winner_data.get("points") or 0)
        loser_current_pts  = float(loser_data.get("points") or 0)

        winner_new_pts = winner_current_pts + payout
        loser_new_pts  = max(0, loser_current_pts - self.bet)

        await update_player_points(winner_data["name"], winner_new_pts)
        await update_player_points(loser_data["name"], loser_new_pts)

        embed = discord.Embed(title="⚔️ Challenge Result", color=discord.Color.gold())
        embed.add_field(
            name="🏆 Winner",
            value=(
                f"{winner_member.mention}\n"
                f"Tier: `{winner_tier}` | Points: `{winner_current_pts:,.2f}` → `{winner_new_pts:,.2f}`\n"
                f"Earned: `+{payout:,.2f}`"
                + (f" *(×{multiplier} upset bonus!)*" if is_upset else "")
            ),
            inline=False
        )
        embed.add_field(
            name="💀 Loser",
            value=(
                f"{loser_member.mention}\n"
                f"Tier: `{loser_tier}` | Points: `{loser_current_pts:,.2f}` → `{loser_new_pts:,.2f}`\n"
                f"Lost: `-{self.bet:,.2f}`"
            ),
            inline=False
        )
        embed.set_footer(text="Made by vlaims • api.kirka.io")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="🏆 Challenger Won", style=discord.ButtonStyle.green, custom_id="challenger_won")
    async def challenger_won(self, interaction: discord.Interaction, button: discord.ui.Button):
        leader_role = discord.utils.get(interaction.guild.roles, name="leader")
        if not leader_role or leader_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only leaders can declare a winner.", ephemeral=True)
            return
        await self.resolve(interaction, self.challenger_member, self.opponent_member,
                           self.challenger_data, self.opponent_data)

    @discord.ui.button(label="🏆 Opponent Won", style=discord.ButtonStyle.blurple, custom_id="opponent_won")
    async def opponent_won(self, interaction: discord.Interaction, button: discord.ui.Button):
        leader_role = discord.utils.get(interaction.guild.roles, name="leader")
        if not leader_role or leader_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only leaders can declare a winner.", ephemeral=True)
            return
        await self.resolve(interaction, self.opponent_member, self.challenger_member,
                           self.opponent_data, self.challenger_data)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, custom_id="cancel_challenge")
    async def cancel_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        leader_role = discord.utils.get(interaction.guild.roles, name="leader")
        is_leader   = leader_role and leader_role in interaction.user.roles
        is_participant = interaction.user.id in [self.challenger_member.id, self.opponent_member.id]
        if not is_leader and not is_participant:
            await interaction.response.send_message("❌ You can't cancel this challenge.", ephemeral=True)
            return
        if self.resolved:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        self.resolved = True
        embed = make_embed("⚔️ Challenge Cancelled", "The challenge was cancelled. No points exchanged.", discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)


class ChallengeAcceptView(discord.ui.View):
    def __init__(self, challenger_data: dict, opponent_data: dict, bet: float,
                 challenger_member: discord.Member, opponent_member: discord.Member):
        super().__init__(timeout=120)
        self.challenger_data   = challenger_data
        self.opponent_data     = opponent_data
        self.bet               = bet
        self.challenger_member = challenger_member
        self.opponent_member   = opponent_member

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green, custom_id="accept_challenge")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_member.id:
            await interaction.response.send_message("❌ This challenge isn't for you.", ephemeral=True)
            return

        result_view = ChallengeResultView(
            challenger_data=self.challenger_data,
            opponent_data=self.opponent_data,
            bet=self.bet,
            challenger_member=self.challenger_member,
            opponent_member=self.opponent_member
        )

        challenger_tier = self.challenger_data.get("tier", "?")
        opponent_tier   = self.opponent_data.get("tier", "?")

        embed = discord.Embed(
            title="⚔️ Challenge Accepted!",
            description=(
                f"{self.challenger_member.mention} **vs** {self.opponent_member.mention}\n\n"
                f"**Bet:** `{self.bet:,.2f}` points\n"
                f"**{self.challenger_member.display_name}'s Tier:** `{challenger_tier}`\n"
                f"**{self.opponent_member.display_name}'s Tier:** `{opponent_tier}`\n\n"
                f"*A leader must declare the winner below.*"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Made by vlaims • api.kirka.io")
        await interaction.response.edit_message(embed=embed, view=result_view)

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red, custom_id="decline_challenge")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_member.id:
            await interaction.response.send_message("❌ This challenge isn't for you.", ephemeral=True)
            return
        embed = make_embed(
            "⚔️ Challenge Declined",
            f"{self.opponent_member.mention} declined the challenge from {self.challenger_member.mention}.",
            discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)


# ─────────────────────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────────────────────

@bot.tree.command(name="challenge", description="Challenge another clan member to a bet")
@app_commands.describe(opponent="The member you want to challenge", bet="How many points to bet")
@cooldown(10)
async def challenge(interaction: discord.Interaction, opponent: discord.Member, bet: float):
    await interaction.response.defer()
    if opponent.id == interaction.user.id:
        await interaction.followup.send("❌ You can't challenge yourself.", ephemeral=True)
        return
    if bet <= 0:
        await interaction.followup.send("❌ Bet must be greater than 0.", ephemeral=True)
        return

    challenger_data = await get_roster_player_by_discord(interaction.user.name)
    opponent_data   = await get_roster_player_by_discord(opponent.name)

    if not challenger_data:
        await interaction.followup.send("❌ You're not registered in the roster.", ephemeral=True)
        return
    if not opponent_data:
        await interaction.followup.send(f"❌ {opponent.display_name} is not registered in the roster.", ephemeral=True)
        return

    challenger_tier = challenger_data.get("tier")
    opponent_tier   = opponent_data.get("tier")

    if not challenger_tier:
        await interaction.followup.send("❌ You don't have a tier assigned yet. Ask a leader to assign one.", ephemeral=True)
        return
    if not opponent_tier:
        await interaction.followup.send(f"❌ {opponent.display_name} doesn't have a tier assigned yet.", ephemeral=True)
        return

    challenger_pts = float(challenger_data.get("points") or 0)
    if challenger_pts < bet:
        await interaction.followup.send(f"❌ You don't have enough points. Your balance: `{challenger_pts:,.2f}`", ephemeral=True)
        return

    opponent_pts = float(opponent_data.get("points") or 0)
    if opponent_pts < bet:
        await interaction.followup.send(f"❌ {opponent.display_name} doesn't have enough points (`{opponent_pts:,.2f}`).", ephemeral=True)
        return

    view = ChallengeAcceptView(
        challenger_data=challenger_data,
        opponent_data=opponent_data,
        bet=bet,
        challenger_member=interaction.user,
        opponent_member=opponent
    )

    embed = discord.Embed(
        title="⚔️ Challenge Issued!",
        description=(
            f"{interaction.user.mention} has challenged {opponent.mention}!\n\n"
            f"**Bet:** `{bet:,.2f}` points\n"
            f"**{interaction.user.display_name}'s Tier:** `{challenger_tier}` *(Balance: `{challenger_pts:,.2f}`)*\n"
            f"**{opponent.display_name}'s Tier:** `{opponent_tier}` *(Balance: `{opponent_pts:,.2f}`)*\n\n"
            f"{opponent.mention}, do you accept?"
        ),
        color=discord.Color.orange()
    )
    embed.set_footer(text="Made by vlaims • api.kirka.io")
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="settier", description="Set a player's tier (leaders only)")
@app_commands.describe(name="Player's roster name", tier="Tier to assign (S, A+, A, B, C, F)")
@app_commands.default_permissions(administrator=True)
@app_commands.autocomplete(name=roster_autocomplete)
async def settier(interaction: discord.Interaction, name: str, tier: str):
    await interaction.response.defer(ephemeral=True)
    tier = tier.strip()
    if tier not in TIER_ORDER:
        await interaction.followup.send(f"❌ Invalid tier `{tier}`. Valid tiers: {', '.join(TIER_ORDER)}", ephemeral=True)
        return

    url = supabase_endpoint(f"roster?name=ilike.{name}")
    try:
        async with http_session.patch(url, headers=supabase_headers(), json={"tier": tier}) as resp:
            if resp.status in [200, 204]:
                await interaction.followup.send(f"✅ Set **{name}**'s tier to `{tier}`.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Failed to update tier. (HTTP {resp.status})", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


@bot.tree.command(name="addpoints", description="Add points to a player (leaders only)")
@app_commands.describe(name="Player's roster name", amount="Points to add")
@app_commands.default_permissions(administrator=True)
@app_commands.autocomplete(name=roster_autocomplete)
async def addpoints(interaction: discord.Interaction, name: str, amount: float):
    await interaction.response.defer(ephemeral=True)
    player = await get_roster_player_by_name(name)
    if not player:
        await interaction.followup.send(f"❌ Player `{name}` not found.", ephemeral=True)
        return
    new_pts = float(player.get("points") or 0) + amount
    success = await update_player_points(player["name"], new_pts)
    if success:
        await interaction.followup.send(f"✅ Added `{amount:,.2f}` points to **{name}**. New balance: `{new_pts:,.2f}`", ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to update points.", ephemeral=True)


@bot.tree.command(name="points", description="Check a player's points and tier")
@app_commands.describe(name="Player name (leave blank for yourself)")
@app_commands.autocomplete(name=roster_autocomplete)
async def points(interaction: discord.Interaction, name: str = None):
    await interaction.response.defer()
    if name:
        player = await get_roster_player_by_name(name)
    else:
        player = await get_roster_player_by_discord(interaction.user.name)

    if not player:
        await interaction.followup.send("❌ Player not found in the roster.", ephemeral=True)
        return

    pts  = float(player.get("points") or 0)
    tier = player.get("tier") or "Unranked"
    embed = make_embed(f"💰 {to_fancy_font(player['name'])}", f"**Tier:** `{tier}`\n**Points:** `{pts:,.2f}`")
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────────────────────────
# ACTIVITY SYSTEM
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="activity", description="Host or join clan activities")
@app_commands.default_permissions(administrator=True) # Only admins can see subcommands by default? No, specific checks inside
async def activity(interaction: discord.Interaction):
    """Base command for activities."""
    pass

@activity.command(name="start", description="Start an activity session")
@app_commands.describe(points="Points awarded to each participant")
async def activity_start(interaction: discord.Interaction, points: float):
    if not (discord.utils.get(interaction.user.roles, name="leader") or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ Only leaders can start activities.", ephemeral=True)
        return
        
    global ACTIVE_ACTIVITY
    if ACTIVE_ACTIVITY["active"]:
        await interaction.response.send_message("❌ An activity is already active! End it first.", ephemeral=True)
        return

    ACTIVE_ACTIVITY["active"] = True
    ACTIVE_ACTIVITY["points"] = points
    ACTIVE_ACTIVITY["participants"] = []
    ACTIVE_ACTIVITY["starter"] = interaction.user.mention

    embed = make_embed(
        "🎉 Activity Started!",
        f"Started by: {interaction.user.mention}\n"
        f"Reward: `{points:,.2f}` points\n\n"
        f"**Use `/activity join` to participate!**",
        color=discord.Color.magenta()
    )
    await interaction.response.send_message(embed=embed)

@activity.command(name="join", description="Join the current activity")
async def activity_join(interaction: discord.Interaction):
    await interaction.response.defer()
    global ACTIVE_ACTIVITY
    
    if not ACTIVE_ACTIVITY["active"]:
        await interaction.followup.send("❌ No active activity right now.", ephemeral=True)
        return

    # Check if user is already in list
    if any(p.id == interaction.user.id for p in ACTIVE_ACTIVITY["participants"]):
        await interaction.followup.send("❌ You already joined this activity.", ephemeral=True)
        return

    ACTIVE_ACTIVITY["participants"].append(interaction.user)
    await interaction.followup.send(f"✅ {interaction.user.mention} joined the activity!", ephemeral=False)

@activity.command(name="end", description="End the activity and distribute points")
async def activity_end(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, name="leader") or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ Only leaders can end activities.", ephemeral=True)
        return

    global ACTIVE_ACTIVITY
    if not ACTIVE_ACTIVITY["active"]:
        await interaction.response.send_message("❌ No active activity to end.", ephemeral=True)
        return

    await interaction.response.defer()
    
    participants = ACTIVE_ACTIVITY["participants"]
    points_awarded = ACTIVE_ACTIVITY["points"]
    
    if not participants:
        ACTIVE_ACTIVITY["active"] = False
        await interaction.followup.send("No one joined the activity. Session ended.")
        return

    success_count = 0
    failed_users = []

    # Process distribution
    for member in participants:
        player_data = await get_roster_player_by_discord(member.name)
        if player_data:
            current_pts = float(player_data.get("points") or 0)
            new_pts = current_pts + points_awarded
            if await update_player_points(player_data["name"], new_pts):
                success_count += 1
            else:
                failed_users.append(member.display_name)
        else:
            failed_users.append(member.display_name)

    ACTIVE_ACTIVITY["active"] = False # Reset state

    embed = discord.Embed(
        title="🏁 Activity Ended",
        description=f"Distributed `{points_awarded}` points to **{success_count}** members.",
        color=discord.Color.green()
    )
    
    # List some winners
    winners_list = "\n".join([p.mention for p in participants[:10]])
    if len(participants) > 10:
        winners_list += f"\n...and {len(participants)-10} others."
        
    embed.add_field(name="Participants", value=winners_list if winners_list else "None", inline=False)
    
    if failed_users:
        embed.add_field(name="Failed to update", value=", ".join(failed_users), inline=False)
        embed.color = discord.Color.orange()

    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────────────────────────
# SHOP SYSTEM
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="shop", description="View the clan shop")
async def shop(interaction: discord.Interaction):
    await interaction.response.defer()
    
    desc = ""
    for key, item in SHOP_ITEMS.items():
        desc += f"**{item['name']}** — `{item['price']:,} pts`\n`ID: {item['id']}`\n_{item['desc']}_\n\n"
    
    embed = make_embed("🛒 Clan Shop", desc, color=discord.Color.purple())
    embed.set_footer(text="Use /buy [item_id] to purchase an item.")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="buy", description="Buy an item from the shop")
@app_commands.describe(item_id="The ID of the item to buy")
async def buy(interaction: discord.Interaction, item_id: str):
    await interaction.response.defer()
    
    if item_id not in SHOP_ITEMS:
        await interaction.followup.send(f"❌ Item ID `{item_id}` not found. Use `/shop` to see items.", ephemeral=True)
        return
    
    item = SHOP_ITEMS[item_id]
    
    # Get player data
    player_data = await get_roster_player_by_discord(interaction.user.name)
    if not player_data:
        await interaction.followup.send("❌ You are not registered in the roster.", ephemeral=True)
        return
    
    current_pts = float(player_data.get("points") or 0)
    
    if current_pts < item['price']:
        await interaction.followup.send(f"❌ You need `{item['price'] - current_pts:,.2f}` more points to buy this.", ephemeral=True)
        return
    
    # Deduct points
    new_pts = current_pts - item['price']
    if await update_player_points(player_data['name'], new_pts):
        embed = discord.Embed(
            title="🛍️ Purchase Successful!",
            description=f"You bought **{item['name']}** for `{item['price']:,}` points.\nNew Balance: `{new_pts:,.2f}`",
            color=discord.Color.gold()
        )
        # Optional: Add logic to give roles here based on item_id
        # e.g., if item_id == "booster": add_role(...)
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send("❌ Transaction failed due to database error.", ephemeral=True)


# ─────────────────────────────────────────────────────────────
# OTHER COMMANDS (Existing functionality maintained)
# ─────────────────────────────────────────────────────────────

@bot.tree.command(name="members", description="Previews all registered data from the Supabase clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with http_session.get(
            supabase_endpoint("roster?select=*&order=name.desc"),
            headers=supabase_headers()
        ) as response:
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
            fancy_name   = to_fancy_font(item.get('name', 'Unknown'))
            player_id    = item.get('player_id', 'N/A')
            discord_user = item.get('discord_handle', 'N/A')
            tier         = item.get('tier') or 'Unranked'
            pts          = float(item.get('points') or 0)
            all_lines.append(
                f"**{index}. {fancy_name}**\n"
                f"- ↳ *ID:* `{player_id}` • *Discord:* `@{discord_user}`\n"
                f"- ↳ *Tier:* `{tier}` • *Points:* `{pts:,.2f}`"
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
    admin_role   = discord.utils.get(interaction.guild.roles, name="leader")
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
@app_commands.autocomplete(name=roster_autocomplete)
async def kick(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    try:
        async with http_session.delete(
            supabase_endpoint(f"roster?name=eq.{name}"),
            headers=supabase_headers()
        ) as response:
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
    try:
        async with http_session.get(
            supabase_endpoint("roster?select=*"),
            headers=supabase_headers()
        ) as response:
            if response.status != 200:
                await interaction.followup.send(f"Database error. (Code: `{response.status}`)")
                return
            roster_data = await response.json()

        if not roster_data:
            await interaction.followup.send("No players found in the roster.")
            return

        total      = len(roster_data)
        status_msg = await interaction.followup.send(f"🔍 Fetching stats for {total} players...")

        tasks    = [kirka_get_profile(p.get('player_id', '').strip()) for p in roster_data]
        profiles = await asyncio.gather(*tasks)

        results = []
        for player, profile in zip(roster_data, profiles):
            name = player.get('name', 'Unknown')
            if profile:
                prp_val = float(profile.get('klo2V2', 0) or 0)
                stats   = profile.get('stats', {})
                kills   = stats.get('kills', 0) or 0
                deaths  = stats.get('deaths', 0) or 1
                kd_val  = round(kills / deaths, 2)
                results.append({'name': name, 'prp': prp_val, 'kd': kd_val, 'found': True})
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


@bot.tree.command(name="topkd", description="Top K/D players in the roster")
async def topkd(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with http_session.get(supabase_endpoint("roster?select=*"), headers=supabase_headers()) as response:
            roster = await response.json()
    except Exception:
        await interaction.followup.send("Error fetching roster.")
        return

    tasks    = [kirka_get_profile(p["player_id"]) for p in roster]
    profiles = await asyncio.gather(*tasks)

    players = []
    for player, profile in zip(roster, profiles):
        if not profile:
            continue
        stats  = profile.get("stats", {})
        kills  = stats.get("kills", 0)
        deaths = stats.get("deaths", 1)
        players.append({"name": player["name"], "kd": round(kills / deaths, 2)})

    players.sort(key=lambda x: x["kd"], reverse=True)
    text = ""
    for i, p in enumerate(players[:10], 1):
        text += f"**{i}.** {to_fancy_font(p['name'])} — `{p['kd']}`\n"

    await interaction.followup.send(embed=make_embed("🎯 Highest K/D Players", text))


@bot.tree.command(name="profile", description="Look up a Kirka player's profile by their short ID")
@app_commands.describe(player_id="The player's short ID (e.g. XMNVRX)")
@cooldown(5)
@app_commands.autocomplete(player_id=roster_autocomplete) # Reusing roster autocomplete for ease of use
async def profile(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()
    # Autocomplete returns Name, but input might be ID. Try Name lookup first for roster convenience
    data = await kirka_get_profile(player_id)
    # If not found, try searching by roster name if the input matches a roster player's ID
    if not data:
        player = await get_roster_player_by_name(player_id)
        if player:
            data = await kirka_get_profile(player.get('player_id'))
            
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
    embed.add_field(name="Level",      value=data.get('level', 'N/A'),              inline=True)
    embed.add_field(name="Clan",       value=data.get('clan') or 'None',             inline=True)
    embed.add_field(name="Role",       value=data.get('role', 'N/A'),               inline=True)
    embed.add_field(name="PRP (2v2)",  value=f"`{prp:,.2f}`",                       inline=True)
    embed.add_field(name="K/D",        value=f"`{kd:.2f}`",                         inline=True)
    embed.add_field(name="Kills",      value=f"`{kills:,}`",                        inline=True)
    embed.add_field(name="Deaths",     value=f"`{stats.get('deaths', 0):,}`",       inline=True)
    embed.add_field(name="Wins",       value=f"`{stats.get('wins', 0):,}`",         inline=True)
    embed.add_field(name="Games",      value=f"`{stats.get('games', 0):,}`",        inline=True)
    embed.add_field(name="Headshots",  value=f"`{stats.get('headshots', 0):,}`",    inline=True)
    embed.add_field(name="Scores",     value=f"`{stats.get('scores', 0):,}`",       inline=True)
    embed.set_footer(text="Data from api.kirka.io | Made by vlaims")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="compare", description="Compare two Kirka players")
@app_commands.autocomplete(player1=roster_autocomplete, player2=roster_autocomplete)
async def compare(interaction: discord.Interaction, player1: str, player2: str):
    await interaction.response.defer()
    
    # Try fetching via Kirka ID directly or roster lookup
    p1_data = await kirka_get_profile(player1)
    if not p1_data:
        p1_roster = await get_roster_player_by_name(player1)
        if p1_roster: p1_data = await kirka_get_profile(p1_roster['player_id'])
            
    p2_data = await kirka_get_profile(player2)
    if not p2_data:
        p2_roster = await get_roster_player_by_name(player2)
        if p2_roster: p2_data = await kirka_get_profile(p2_roster['player_id'])

    if not p1_data or not p2_data:
        await interaction.followup.send("❌ Failed to fetch one or both players.")
        return

    def kd(stats):
        return round(stats.get("kills", 0) / max(stats.get("deaths", 1), 1), 2)

    embed = make_embed(f"⚔️ {p1_data['name']} vs {p2_data['name']}")
    embed.add_field(
        name=p1_data["name"],
        value=f"Level: `{p1_data.get('level', 0)}`\nKD: `{kd(p1_data['stats'])}`\nPRP: `{p1_data.get('klo2V2', 0):,.2f}`",
        inline=True
    )
    embed.add_field(
        name=p2_data["name"],
        value=f"Level: `{p2_data.get('level', 0)}`\nKD: `{kd(p2_data['stats'])}`\nPRP: `{p2_data.get('klo2V2', 0):,.2f}`",
        inline=True
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="claninfo", description="Show Kiss clan info and member list from Kirka")
async def claninfo(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await kirka_get_clan("kiss")
    if not data:
        await interaction.followup.send("❌ Could not fetch clan data from Kirka.")
        return
    members_list   = data.get('members', [])
    members_sorted = sorted(members_list, key=lambda m: m.get('monthScores', 0), reverse=True)

    overview = discord.Embed(
        title=f"🏰 Clan: {data.get('name', 'kiss').upper()}",
        description=data.get('description') or '',
        color=discord.Color.from_rgb(63, 207, 142)
    )
    overview.add_field(name="Members",        value=f"`{len(members_list)}`",                           inline=True)
    overview.add_field(name="Clan War Rank",   value=f"`#{data.get('currentClanWarPosition', '?')}`",   inline=True)
    overview.add_field(name="Month Scores",    value=f"`{data.get('monthScores', 0):,}`",               inline=True)
    overview.add_field(name="All-Time Scores", value=f"`{data.get('allScores', 0):,}`",                 inline=True)
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
    view  = PaginationView(pages=pages, title="🏰 Kiss Clan Members", total_label=f"Total Members: {len(members_list)}")
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
        lines.append(f"{medal} **{fancy_name}** `#{short_id}`\n┗ PRP: `{prp:,.2f}`")

    pages = ["\n\n".join(lines[i:i+10]) for i in range(0, len(lines), 10)]
    title = "🏆 Global Ranked 2v2 Leaderboard" + (f" — Season {season}" if season else "")
    view  = PaginationView(pages=pages, title=title)
    await interaction.followup.send(embed=view.create_embed(), view=view)


# ─────────────────────────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────────────────────────
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandNotFound):
        return # Ignore unknown commands
    
    print(f"[ERROR] {error}")
    try:
        msg = "❌ Something went wrong executing that command."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as: {bot.user}")
    print(f"Servers: {len(bot.guilds)}")
    print("=" * 50)


# ─────────────────────────────────────────────────────────────
# ENV CHECK + RUN
# ─────────────────────────────────────────────────────────────
for var in ["DISCORD_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]:
    if not os.environ.get(var):
        raise RuntimeError(f"Missing environment variable: {var}")

bot.run(os.environ.get('DISCORD_TOKEN'))