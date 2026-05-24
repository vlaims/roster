import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import re

# 🎨 HELPER FUNCTION: Maps standard characters to a Fancy Bold Serif Font Style
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


# ----------------------------------------------------
# 🌐 HELPER FUNCTION: FETCH PLAYER STATS FROM KIRKA.IO API
# ----------------------------------------------------
async def fetch_player_stats(player_id: str):
    """
    Fetches PRP and KD from the Kirka.io internal player API endpoint.
    
    The network response object is named wWNmMWnm and contains:
      - wWwnNmMW  → PRP  (Ranked 2v2 Points, e.g. 267.96)
      - wnWNmwWM  → KD raw integer; divide by 1000 to get the real K/D (e.g. 1000 → 1.000, 830 → 0.83)
    
    Returns a dict: { 'prp': float, 'kd': float } or None on failure.
    """
    # Strip the # prefix if the ID was stored with one
    clean_id = player_id.replace('#', '').strip()
    if not clean_id:
        return None

    # ----------------------------------------------------------------
    # The Kirka.io profile page at /profile/<ID> fires a Fetch/XHR
    # request to retrieve the player object (visible in DevTools as
    # wWNmMWnw).  The endpoint pattern observed in the network tab is:
    #   https://kirka.io/player/<clean_id>
    # ----------------------------------------------------------------
    url = f"https://kirka.io/player/{clean_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': f'https://kirka.io/profile/{clean_id}',
        'Origin': 'https://kirka.io',
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    print(f"[Kirka] HTTP {response.status} for player {clean_id}")
                    return None

                # The endpoint returns JSON — the root object is wWNmMWnm
                data = await response.json(content_type=None)

                # ── Pull the obfuscated field names ──────────────────────────
                # wWNmMWnm is the root wrapper; navigate into it
                player_obj = data.get('wWNmMWnm', data)  # fall back to root if already unwrapped

                # PRP: wWwnNmMW
                prp_raw = player_obj.get('wWwnNmMW')
                # KD:  wnWNmwWM  (raw integer → divide by 1000)
                kd_raw  = player_obj.get('wnWNmwWM')

                if prp_raw is None and kd_raw is None:
                    print(f"[Kirka] Fields not found in response for {clean_id}. Keys: {list(player_obj.keys())}")
                    return None

                prp = float(prp_raw) if prp_raw is not None else 0.0
                kd  = float(kd_raw)  / 1000.0 if kd_raw  is not None else 0.0

                print(f"[Kirka] {clean_id} → PRP={prp}, KD={kd}")
                return {'prp': prp, 'kd': kd}

    except Exception as e:
        print(f"[Kirka] Error fetching stats for {clean_id}: {e}")
        return None


# ----------------------------------------------------
# 📄 PAGINATION VIEW: HANDLES ROSTER PAGES (<-- -->)
# ----------------------------------------------------
class RosterPaginationView(discord.ui.View):
    def __init__(self, pages: list, total_players: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.total_players = total_players
        self.current_page = 0
        
        self.prev_page_btn.disabled = True
        if len(self.pages) <= 1:
            self.next_page_btn.disabled = True

    def create_embed(self):
        embed = discord.Embed(
            title="Kiss Clan Players",
            description=f"### Total Tracked Players: {self.total_players}\n\n" + self.pages[self.current_page],
            color=discord.Color.from_rgb(63, 207, 142)
        )
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)} | Made by vlaims")
        return embed

    @discord.ui.button(label="<--", style=discord.ButtonStyle.green, custom_id="prev_page_btn")
    async def prev_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
        self.next_page_btn.disabled = False
        if self.current_page == 0:
            button.disabled = True
        await interaction.edit_original_response(embed=self.create_embed(), view=self)

    @discord.ui.button(label="-->", style=discord.ButtonStyle.green, custom_id="next_page_btn")
    async def next_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        self.prev_page_btn.disabled = False
        if self.current_page == len(self.pages) - 1:
            button.disabled = True
        await interaction.edit_original_response(embed=self.create_embed(), view=self)


# ----------------------------------------------------
# 🔘 INTERACTIVE PANEL: ADMIN APPROVAL BUTTONS
# ----------------------------------------------------
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
        payload = {
            "name": self.name,
            "discord_handle": self.discord_handle,
            "player_id": self.player_id
        }

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
                try:
                    await member.send("Your application got rejected your a fucking chud get better 😂😂😂")
                except discord.Forbidden:
                    print(f"Could not send DM to {self.discord_handle} (DMs locked or blocked)")
        
        await interaction.edit_original_response(embed=embed, view=None)


# ----------------------------------------------------
# COMMAND 1: THE MEMBERS ROSTER LOOKUP (PAGINATED & SORTED)
# ----------------------------------------------------
@bot.tree.command(name="members", description="Previews all registered data from the Supabase clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        await interaction.followup.send("Error: Supabase credentials are missing in Railway Environment Variables.")
        return

    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?select=*&order=name.desc"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(target_endpoint, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(f"Error communicating with Supabase database. (Code: `{response.status}`)")
                    return
                raw_data = await response.json()
                
        if not raw_data or not isinstance(raw_data, list):
            await interaction.followup.send("Connection successful! However, your Supabase roster table is currently empty.")
            return

        total_players = len(raw_data)
        
        vlaims_record = None
        other_records = []
        for item in raw_data:
            if str(item.get('name', '')).lower() == 'vlaims':
                vlaims_record = item
            else:
                other_records.append(item)
                
        sorted_dataset = []
        if vlaims_record:
            sorted_dataset.append(vlaims_record)
        sorted_dataset.extend(other_records)

        all_lines = []
        for index, item in enumerate(sorted_dataset, 1):
            raw_name = item.get('name', 'Unknown')
            discord_user = item.get('discord_handle', 'N/A')
            player_id = item.get('player_id', 'N/A')
            fancy_name = to_fancy_font(raw_name)
            all_lines.append(f"**{index}. {fancy_name}**\n- # ↳ *ID:* `{player_id}` • *Discord:* `@{discord_user}`")
            
        pages_content = []
        for i in range(0, len(all_lines), 5):
            chunk = all_lines[i:i+5]
            pages_content.append("\n".join(chunk))
            
        view = RosterPaginationView(pages=pages_content, total_players=total_players)
        await interaction.followup.send(embed=view.create_embed(), view=view)
        
    except Exception as e:
        print(f"SUPABASE FETCH ERROR: {e}")
        await interaction.followup.send("Failed to parse data from your Supabase cloud repository.")


# ----------------------------------------------------
# COMMAND 2: THE /REGISTER COMMAND WITH CHANNEL GATING
# ----------------------------------------------------
@bot.tree.command(name="register", description="Apply to join the clan")
@app_commands.describe(name="Your name", player_id="Your in-game ID")
async def register(interaction: discord.Interaction, name: str, player_id: str):
    if interaction.channel.name not in ["apply", "general"]:
        await interaction.response.send_message("Use this command in `#apply` or `#general`.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    logs_channel = discord.utils.get(interaction.guild.text_channels, name="application-logs")
    admin_role = discord.utils.get(interaction.guild.roles, name="smooch")

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


# ----------------------------------------------------
# COMMAND 3: THE ADMIN /KICK REMOVAL COMMAND
# ----------------------------------------------------
@bot.tree.command(name="kick", description="Remove a player from the roster")
@app_commands.default_permissions(administrator=True)
async def kick(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?name=eq.{name}"
    headers = {
        "apikey": supabase_key, 
        "Authorization": f"Bearer {supabase_key}", 
        "Prefer": "return=representation"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(target_endpoint, headers=headers) as response:
                if response.status == 200:
                    deleted_data = await response.json()
                    if not deleted_data:
                        await interaction.followup.send(f"Could not find a player named `{name}` in the database.")
                        return
                    
                    fancy_kicked_name = to_fancy_font(name)
                    embed = discord.Embed(
                        title="Player Removed",
                        description=f"**{fancy_kicked_name}** has been successfully scrubbed from the clan database roster.",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"Failed to delete player. (HTTP Error: `{response.status}`)")
    except Exception as e:
        await interaction.followup.send(f"Critical error: {e}")


# ----------------------------------------------------
# COMMAND 4: CHECK PRP & KD FOR ALL ROSTER PLAYERS
# ----------------------------------------------------
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

        status_msg = await interaction.followup.send(
            f"🔍 Fetching stats for {len(roster_data)} players... This may take a moment."
        )

        results = []
        for idx, player in enumerate(roster_data, 1):
            player_id = player.get('player_id', '').strip()
            name      = player.get('name', 'Unknown')
            
            if idx % 5 == 0:
                try:
                    await status_msg.edit(content=f"🔍 Fetching stats... ({idx}/{len(roster_data)} players)")
                except Exception:
                    pass

            if player_id:
                stats = await fetch_player_stats(player_id)
                results.append({
                    'name':      name,
                    'player_id': player_id,
                    'prp':       stats['prp'] if stats else 0.0,
                    'kd':        stats['kd']  if stats else 0.0,
                    'found':     stats is not None,
                })
            else:
                results.append({
                    'name':      name,
                    'player_id': 'N/A',
                    'prp':       0.0,
                    'kd':        0.0,
                    'found':     False,
                })

        # Sort by PRP highest first
        results.sort(key=lambda x: x['prp'], reverse=True)

        embed = discord.Embed(
            title="🏆 Ranked 2v2 Leaderboard",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for idx, p in enumerate(results, 1):
            fancy_name = to_fancy_font(p['name'])

            if not p['found']:
                prp_display = "N/A"
                kd_display  = "N/A"
            else:
                prp_display = f"{p['prp']:,.2f}"
                kd_display  = f"{p['kd']:.2f}"

            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = f"**{idx}.**"

            # PRP shown first, then K/D
            leaderboard_text += (
                f"{medal} **{fancy_name}**\n"
                f"┣ PRP: `{prp_display}`\n"
                f"┗ K/D: `{kd_display}`\n\n"
            )

        embed.description = leaderboard_text
        embed.set_footer(text="Data fetched from kirka.io | Made by vlaims")

        await status_msg.edit(content=None, embed=embed)
        
    except Exception as e:
        print(f"PRP COMMAND ERROR: {e}")
        await interaction.followup.send(f"Failed to fetch stats: {e}")


bot.run(os.environ.get('DISCORD_TOKEN'))