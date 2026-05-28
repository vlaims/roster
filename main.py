import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

# ─────────────────────────────────────────────────────────────
# CONFIG
# Set KIRKA_API_KEY in Railway environment variables.
# ─────────────────────────────────────────────────────────────
KIRKA_API_KEY  = os.environ.get('KIRKA_API_KEY', '573d64dc39e83332e2237c1fd5fc2a991958c4d0225bcfbd307ee2a3a456d473')
KIRKA_BASE_URL = "https://api.kirka.io"

def kirka_headers():
    return {
        "ApiKey": KIRKA_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# 🎨 HELPER: Fancy Bold Serif font mapper
def to_fancy_font(text):
    normal_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy_chars  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    trans = str.maketrans(normal_chars, fancy_chars)
    return str(text).translate(trans)


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)


bot = MyBot()


# ─────────────────────────────────────────────────────────────
# 🌐 KIRKA API HELPERS
# ─────────────────────────────────────────────────────────────
async def kirka_get_profile(short_id: str):
    """POST /api/user/getProfile — returns full profile dict or None."""
    clean_id = short_id.replace('#', '').strip()
    if not clean_id:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{KIRKA_BASE_URL}/api/user/getProfile",
                headers=kirka_headers(),
                json={"id": clean_id, "isShortId": True},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 201:
                    return await resp.json()
                body = await resp.text()
                print(f"[Kirka] getProfile {clean_id} → HTTP {resp.status} | {body[:200]}")
                return None
    except Exception as e:
        print(f"[Kirka] getProfile error for {clean_id}: {e}")
        return None


async def kirka_get_clan(clan_name: str):
    """GET /api/clan/{name} — returns clan dict or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KIRKA_BASE_URL}/api/clan/{clan_name}",
                headers=kirka_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                body = await resp.text()
                print(f"[Kirka] getClan {clan_name} → HTTP {resp.status} | {body[:200]}")
                return None
    except Exception as e:
        print(f"[Kirka] getClan error: {e}")
        return None


async def kirka_get_ranked2v2():
    """GET /api/leaderboard/ranked2V2 — returns leaderboard dict or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KIRKA_BASE_URL}/api/leaderboard/ranked2V2",
                headers=kirka_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                body = await resp.text()
                print(f"[Kirka] ranked2V2 → HTTP {resp.status} | {body[:200]}")
                return None
    except Exception as e:
        print(f"[Kirka] ranked2V2 error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 📄 PAGINATION VIEW
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
# 🔘 ADMIN APPROVAL BUTTONS
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
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        payload = {"name": self.name, "discord_handle": self.discord_handle, "player_id": self.player_id}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(target_endpoint, headers=headers, json=payload) as response:
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
                # Add "declined" role
                declined_role = discord.utils.get(guild.roles, name="declined")
                if declined_role:
                    await member.add_roles(declined_role)
                # Remove "applicator" role if they have it
                applicator_role = discord.utils.get(guild.roles, name="applicator")
                if applicator_role:
                    await member.remove_roles(applicator_role)
                try:
                    await member.send("Your application got rejected your a fucking chud get better 😂😂😂")
                except discord.Forbidden:
                    pass
        await interaction.edit_original_response(embed=embed, view=None)


# ─────────────────────────────────────────────────────────────
# COMMAND 1: /members — Roster from Supabase
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="members", description="Previews all registered data from the Supabase clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if not supabase_url or not supabase_key:
        await interaction.followup.send("Error: Supabase credentials are missing.")
        return
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?select=*&order=name.desc"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
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


# ─────────────────────────────────────────────────────────────
# COMMAND 2: /register
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="register", description="Apply to join the clan")
@app_commands.describe(name="Your name", player_id="Your in-game ID")
async def register(interaction: discord.Interaction, name: str, player_id: str):
    if interaction.channel.name not in ["apply", "general"]:
        await interaction.response.send_message("Use this command in `#apply` or `#general`.", ephemeral=True)
        return
    # Check applicator role
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


# ─────────────────────────────────────────────────────────────
# COMMAND 3: /kick
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="kick", description="Remove a player from the roster")
@app_commands.default_permissions(administrator=True)
async def kick(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?name=eq.{name}"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}", "Prefer": "return=representation"}
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


# ─────────────────────────────────────────────────────────────
# COMMAND 4: /prp — PRP + K/D for all roster players
# Fetches each player's profile from the public Kirka API.
# PRP = klo2V2, K/D = stats.kills / stats.deaths
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="prp", description="Check Ranked 2v2 Points and K/D for all roster players")
async def prp(interaction: discord.Interaction):
    await interaction.response.defer()
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if not supabase_url or not supabase_key:
        await interaction.followup.send("Error: Supabase credentials are missing.")
        return
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?select=*"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
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
                except Exception:
                    pass
            if player_id:
                profile = await kirka_get_profile(player_id)
                if profile:
                    prp_val = float(profile.get('klo2V2', 0) or 0)
                    stats   = profile.get('stats', {})
                    kills   = stats.get('kills', 0) or 0
                    deaths  = stats.get('deaths', 0) or 1  # avoid div/0
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


# ─────────────────────────────────────────────────────────────
# COMMAND 5: /profile — Look up any player's full profile
# ─────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# COMMAND 6: /claninfo — Info + members for the Kiss clan
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="claninfo", description="Show Kiss clan info and member list from Kirka")
async def claninfo(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await kirka_get_clan("kiss")
    if not data:
        await interaction.followup.send("❌ Could not fetch clan data from Kirka.")
        return
    members = data.get('members', [])
    members_sorted = sorted(members, key=lambda m: m.get('monthScores', 0), reverse=True)
    # Overview embed
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
    # Build member pages (5 per page)
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


# ─────────────────────────────────────────────────────────────
# COMMAND 7: /ranked2v2 — Global Kirka ranked 2v2 leaderboard
# ─────────────────────────────────────────────────────────────
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


bot.run(os.environ.get('DISCORD_TOKEN'))