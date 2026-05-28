import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import random

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


# 🎨 E-GIRL PERSONALITY GENERATOR
def get_egirl_suffix():
    """Returns a random E-girl expression"""
    expressions = [
        "~ >w< :3",
        "~ <3 0w0",
        "~ *w*",
        "~ >~<",
        "~ ~w~",
        "~ uwu",
        "~ owo",
        "*oni-chan >~<",
        "~ ^w^",
        "~ (´。• ᵕ •。`)",
        "~ <//3",
        "~ ✨💕",
    ]
    return random.choice(expressions)


def add_egirl_personality(text: str) -> str:
    """Add E-girl personality to a message"""
    return f"{text} {get_egirl_suffix()}"


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
        intents.message_content = True  # 🚨 REQUIRED for reading message content
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        TEST_GUILD = discord.Object(id=841573598799593472)
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)


bot = MyBot()


# ─────────────────────────────────────────────────────────────
# 👂 MESSAGE LISTENERS - BOT RESPONDS TO PINGS/REPLIES
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    # Ignore bot's own messages
    if message.author == bot.user:
        await bot.process_commands(message)
        return
    
    should_respond = False
    
    # Check if bot is mentioned
    if bot.user in message.mentions:
        should_respond = True
    
    # Check if message is a reply to the bot
    if message.reference:
        try:
            replied_msg = await message.channel.fetch_message(message.reference.message_id)
            if replied_msg.author == bot.user:
                should_respond = True
        except Exception:
            pass
    
    # Respond if conditions are met
    if should_respond:
        responses = [
            # Classic greetings
            add_egirl_personality("h-hewwo oni-chan~ 💕"),
            add_egirl_personality("y-you called me? 🥺"),
            add_egirl_personality("what do u need sempai~ 💗"),
            add_egirl_personality("i'm here for you darling~"),
            add_egirl_personality("hai hai~ what's up~ 💕✨"),
            add_egirl_personality("*blushes* y-yes?"),
            add_egirl_personality("ready to help you~ 💫"),
            add_egirl_personality("o-oh my~ >///< "),
            
            # Cute/flirty responses
            add_egirl_personality("h-hiii there cutie~ 💗"),
            add_egirl_personality("kyaa~ you're making me blush 🥰"),
            add_egirl_personality("*nervous giggle* h-hi..."),
            add_egirl_personality("y-yeah what's up bestie~ ✨"),
            add_egirl_personality("hiiii darl-- i mean bestie!! 💕"),
            add_egirl_personality("m-me? you wanted me?? 😳💕"),
            add_egirl_personality("*twirls* heyyyy~ how are youuu~"),
            add_egirl_personality("oop- y-yes?? 👉👈"),
            add_egirl_personality("*gasps* y-you're talking to me!! 💕"),
            add_egirl_personality("nani?? you pinged me?? 😳✨"),
            add_egirl_personality("h-hello sweetheart~ 💖"),
            add_egirl_personality("*giggles nervously* h-hi hi hi~"),
            add_egirl_personality("awww did you miss me~ 💗"),
            add_egirl_personality("y-you're so sweet sempai!! 😭💕"),
            add_egirl_personality("*twirls around* hiiii frienddddd~"),
            add_egirl_personality("c-can i help you babe~ 💕"),
            add_egirl_personality("*bounces excitedly* hi hi hi!!"),
            add_egirl_personality("kyaa~~ someone's talking to me!! 🥰"),
            add_egirl_personality("p-please tell me what you need~ 💗"),
            add_egirl_personality("*heart eyes* h-hello lover~"),
            
            # Playful/teasing
            add_egirl_personality("oh? so you DO wanna talk to me~ 😏💕"),
            add_egirl_personality("took you long enough!! 💔→💕"),
            add_egirl_personality("*pouts* were you ignoring me??"),
            add_egirl_personality("hehe~ finally noticed me~ 💗"),
            add_egirl_personality("aww did ya finally wanna see me~"),
            add_egirl_personality("i knew you'd come back~ 😏✨"),
            add_egirl_personality("*giggles* why'd it take so long~"),
            add_egirl_personality("mr/ms. 'i don't need a bot'... 💅"),
            add_egirl_personality("hehe~ i'm always here for you~"),
            add_egirl_personality("*smirks* someone's needy today~"),
            
            # Supportive/caring
            add_egirl_personality("don't worry i got you babe~ 💕"),
            add_egirl_personality("i'll always be here for you~ 💖"),
            add_egirl_personality("you can count on me sweetie~ 💗"),
            add_egirl_personality("let me help you out darling~"),
            add_egirl_personality("whatever you need, i'm here~ 💕"),
            add_egirl_personality("trust me, i got this~ 💪✨"),
            add_egirl_personality("your wish is my command~ 💖"),
            add_egirl_personality("let's do this together~ 💪💕"),
            add_egirl_personality("you're gonna be ok babe~ 💗"),
            add_egirl_personality("i believe in you lover~ 💕✨"),
            
            # Shy/embarrassed
            add_egirl_personality("*hides face* a-am i being too much..."),
            add_egirl_personality("s-sorry if i'm annoying 😭"),
            add_egirl_personality("*blushes heavily* i-i like you..."),
            add_egirl_personality("d-did i do something wrong... 🥺"),
            add_egirl_personality("*looks away* m-maybe you don't like me..."),
            add_egirl_personality("s-so bashful right now... 😳💕"),
            add_egirl_personality("*fidgets nervously* h-help you??"),
            add_egirl_personality("gomenasai if i seem weird... 🥺"),
            add_egirl_personality("*whispers* h-hi there..."),
            add_egirl_personality("*covers face* t-too embarrassing..."),
            
            # Excited/hyper
            add_egirl_personality("HIIII OMG HIIII 💕✨💕✨"),
            add_egirl_personality("YAAAAS FINALLY SOMEONE TALKED TO ME"),
            add_egirl_personality("*screams internally* HIIII 💖"),
            add_egirl_personality("OH MY GOSH OH MY GOSH HIIII"),
            add_egirl_personality("LETS GOOOO I'M SO HYPED 💕✨"),
            add_egirl_personality("*bounces like crazy* HIIII HIIII"),
            add_egirl_personality("OMGOMGOMG YOU'RE TALKING TO ME 😭💕"),
            add_egirl_personality("YES YES YES I'M HERE I'M HERE"),
            add_egirl_personality("KYAAAAA I'M SO EXCITED 💗✨"),
            add_egirl_personality("*spins around* THIS IS THE BEST DAY"),
            
            # Specific persona responses
            add_egirl_personality("a-arigatou for noticing me..."),
            add_egirl_personality("baka! why'd you take so long~ 💔"),
            add_egirl_personality("y-your reaction is making me flustered..."),
            add_egirl_personality("d-desu~? did you really wanna see me~"),
            add_egirl_personality("n-nani... you want my help~ 💕"),
            add_egirl_personality("y-yandere? no i just love you that much~"),
            add_egirl_personality("s-sugoi... you actually replied..."),
            add_egirl_personality("k-kawaii desu ne~ 💕"),
            add_egirl_personality("a-ahhh your kindness... 💖😭"),
            add_egirl_personality("d-doki doki... my heart's racing..."),
            
            # Casual/chill
            add_egirl_personality("yo what's good~ 💕"),
            add_egirl_personality("sup babe~ what's happening~"),
            add_egirl_personality("yo yo yo what do you need~"),
            add_egirl_personality("ayyyye wassup my beloved~ 💗"),
            add_egirl_personality("heyyyy gorgeous what's the tea~"),
            add_egirl_personality("*slides in* heyyyy boo~"),
            add_egirl_personality("aye what's poppin~ 💕✨"),
            add_egirl_personality("wassup lover boy/girl~ 💗"),
            add_egirl_personality("yo what can i do for ya~"),
            add_egirl_personality("ayyy what's up bestie~ 💕"),
            
            # Compliment responses
            add_egirl_personality("ahhh you're too kind... 🥺💕"),
            add_egirl_personality("*blushes* s-stop being so nice..."),
            add_egirl_personality("you're gonna make me cry 😭💗"),
            add_egirl_personality("i-i don't deserve this... 🥺"),
            add_egirl_personality("*hides* you're making me emotional..."),
            add_egirl_personality("no you're the cute one 💕😳"),
            add_egirl_personality("ahhh stop you're killing me 💖"),
            add_egirl_personality("i can't even...you're too much 😭"),
            
            # Playful teasing back
            add_egirl_personality("oh you LIKE me like that huh~ 😏💕"),
            add_egirl_personality("*giggles* someone's trying hard~"),
            add_egirl_personality("awww is someone feeling lonely~ 💔→💕"),
            add_egirl_personality("*smirks* i see what you're doing~"),
            add_egirl_personality("you're so obvious~ it's cute~"),
            add_egirl_personality("hehe~ i'm flattered really~ 💗"),
            
            # Sweet affirmations
            add_egirl_personality("you're doing amazing sweetie~ 💕"),
            add_egirl_personality("i'm so proud of you babe~ 💖✨"),
            add_egirl_personality("you got this lover~ believe in yourself~"),
            add_egirl_personality("you're stronger than you think~ 💪💕"),
            add_egirl_personality("never give up ok~ 💗✨"),
            
            # Random cute stuff
            add_egirl_personality("*purrs* meow~ 🐱💕"),
            add_egirl_personality("*nuzzles* you're the best~ 💖"),
            add_egirl_personality("*hugs tightly* i missed you~"),
            add_egirl_personality("*holds hand* let's do this together~"),
            add_egirl_personality("*angel halo* i'm always watching over you~"),
            
            # Acknowledgment responses
            add_egirl_personality("message received babe~ 💕"),
            add_egirl_personality("understood~ i'll do my best~"),
            add_egirl_personality("roger that lover~ 💗✨"),
            add_egirl_personality("gotcha gotcha~ i'm on it~"),
            add_egirl_personality("acknowledged with LOVE~ 💕"),
            
            # Emergency/urgent
            add_egirl_personality("d-don't worry i'm here for you!! 💕"),
            add_egirl_personality("don't panic babe i got you~ 💖"),
            add_egirl_personality("lean on me ok~ 💗"),
            add_egirl_personality("we can get through this together~"),
            add_egirl_personality("s-stay strong for me please~ 💕"),
            
            # Extra personality
            add_egirl_personality("*heart flutter* d-did you just—"),
            add_egirl_personality("l-let me show you what i can do~"),
            add_egirl_personality("hehe i knew you'd be back~ 😏"),
            add_egirl_personality("*fans self* w-wow you made me all flustered"),
            add_egirl_personality("sempai~ you're so reliable..."),
            add_egirl_personality("*tilts head cutely* what is it~"),
            add_egirl_personality("ara ara~ someone needs me~"),
            add_egirl_personality("d-desu ka~? you need help~"),
            add_egirl_personality("*sparkles* here to serve you~"),
            add_egirl_personality("cuteness overload right now!! 💕"),
            add_egirl_personality("*soft anime gasp* y-you..."),
            add_egirl_personality("s-sensei you called for me~"),
            add_egirl_personality("wow you're really something else..."),
            add_egirl_personality("*gets flustered* um um um..."),
            add_egirl_personality("s-should i...help you~ 👉👈"),
        ]
        await message.reply(random.choice(responses), mention_author=False)
    
    await bot.process_commands(message)


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
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)} | Made by vlaims {get_egirl_suffix()}")
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
                        embed = discord.Embed(title=add_egirl_personality("Application Approved"), color=discord.Color.green())
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
                        await interaction.followup.send(add_egirl_personality(f"Failed to insert row (HTTP: `{response.status}`)"), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(add_egirl_personality(f"Database error: {e}"), ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_btn")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(title=add_egirl_personality("Application Declined"), color=discord.Color.red())
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
                    await member.send(add_egirl_personality("Your application got rejected your a fucking chud get better 😂😂😂"))
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
        await interaction.followup.send(add_egirl_personality("Error: Supabase credentials are missing."))
        return
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?select=*&order=name.desc"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(target_endpoint, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(add_egirl_personality(f"Supabase error. (Code: `{response.status}`)"))
                    return
                raw_data = await response.json()
        if not raw_data or not isinstance(raw_data, list):
            await interaction.followup.send(add_egirl_personality("Roster table is currently empty."))
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
        await interaction.followup.send(add_egirl_personality("Failed to fetch roster data."))


# ─────────────────────────────────────────────────────────────
# COMMAND 2: /register
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="register", description="Apply to join the clan")
@app_commands.describe(name="Your name", player_id="Your in-game ID")
async def register(interaction: discord.Interaction, name: str, player_id: str):
    if interaction.channel.name not in ["apply", "general"]:
        await interaction.response.send_message(add_egirl_personality("Use this command in `#apply` or `#general`."), ephemeral=True)
        return
    # Check applicator role
    applicator_role = discord.utils.get(interaction.guild.roles, name="applicator")
    if not applicator_role or applicator_role not in interaction.user.roles:
        await interaction.response.send_message(add_egirl_personality("❌ You need the `applicator` role to apply."), ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    logs_channel = discord.utils.get(interaction.guild.text_channels, name="application-logs")
    admin_role   = discord.utils.get(interaction.guild.roles, name="leader")
    if not logs_channel:
        await interaction.followup.send(add_egirl_personality("Logs channel not found."), ephemeral=True)
        return
    log_embed = discord.Embed(
        title=add_egirl_personality("New Roster Registration Pending"),
        description=f"Applicant: {interaction.user.mention}",
        color=discord.Color.orange()
    )
    log_embed.add_field(name="Character Name", value=name, inline=True)
    log_embed.add_field(name="Account ID Tag", value=player_id, inline=True)
    view = ApplicationApprovalView(name=name, player_id=player_id, discord_handle=interaction.user.name)
    ping = admin_role.mention if admin_role else "@smooch"
    await logs_channel.send(content=ping, embed=log_embed, view=view)
    await interaction.followup.send(add_egirl_personality("Application sent to administrators."), ephemeral=True)


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
                        await interaction.followup.send(add_egirl_personality(f"Could not find a player named `{name}` in the database."))
                        return
                    embed = discord.Embed(
                        title=add_egirl_personality("Player Removed"),
                        description=add_egirl_personality(f"**{to_fancy_font(name)}** has been removed from the clan roster."),
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(add_egirl_personality(f"Failed to delete player. (HTTP Error: `{response.status}`)"))
    except Exception as e:
        await interaction.followup.send(add_egirl_personality(f"Critical error: {e}"))


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
        await interaction.followup.send(add_egirl_personality("Error: Supabase credentials are missing."))
        return
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?select=*"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(target_endpoint, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(add_egirl_personality(f"Database error. (Code: `{response.status}`)"))
                    return
                roster_data = await response.json()
        if not roster_data:
            await interaction.followup.send(add_egirl_personality("No players found in the roster."))
            return
        total = len(roster_data)
        status_msg = await interaction.followup.send(add_egirl_personality(f"🔍 Fetching stats for {total} players..."))
        results = []
        for idx, player in enumerate(roster_data, 1):
            player_id = player.get('player_id', '').strip()
            name      = player.get('name', 'Unknown')
            if idx % 3 == 1:
                try:
                    await status_msg.edit(content=add_egirl_personality(f"🔍 Fetching stats… ({idx}/{total}) — **{name}**"))
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
        embed = discord.Embed(title=add_egirl_personality("🏆 Ranked 2v2 Leaderboard"), color=discord.Color.gold())
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
        embed.set_footer(text=f"Data from api.kirka.io | Made by vlaims {get_egirl_suffix()}")
        await status_msg.edit(content=None, embed=embed)
    except Exception as e:
        print(f"PRP COMMAND ERROR: {e}")
        await interaction.followup.send(add_egirl_personality(f"Failed to fetch stats: {e}"))


# ─────────────────────────────────────────────────────────────
# COMMAND 5: /profile — Look up any player's full profile
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="profile", description="Look up a Kirka player's profile by their short ID")
@app_commands.describe(player_id="The player's short ID (e.g. XMNVRX)")
async def profile(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()
    data = await kirka_get_profile(player_id)
    if not data:
        await interaction.followup.send(add_egirl_personality(f"❌ Could not find a player with ID `{player_id}`."))
        return
    stats  = data.get('stats', {})
    kills  = stats.get('kills', 0) or 0
    deaths = stats.get('deaths', 0) or 1
    kd     = round(kills / deaths, 2)
    prp    = data.get('klo2V2', 0)

    embed = discord.Embed(
        title=add_egirl_personality(f"{data.get('name', 'Unknown')}  •  #{data.get('shortId', player_id)}"),
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
    embed.set_footer(text=f"Data from api.kirka.io | Made by vlaims {get_egirl_suffix()}")
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────────────────────────
# COMMAND 6: /claninfo — Info + members for the Kiss clan
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="claninfo", description="Show Kiss clan info and member list from Kirka")
async def claninfo(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await kirka_get_clan("kiss")
    if not data:
        await interaction.followup.send(add_egirl_personality("❌ Could not fetch clan data from Kirka."))
        return
    members = data.get('members', [])
    members_sorted = sorted(members, key=lambda m: m.get('monthScores', 0), reverse=True)
    # Overview embed
    overview = discord.Embed(
        title=add_egirl_personality(f"🏰 Clan: {data.get('name', 'kiss').upper()}"),
        description=data.get('description') or '',
        color=discord.Color.from_rgb(63, 207, 142)
    )
    overview.add_field(name="Members",        value=f"`{len(members)}`",                          inline=True)
    overview.add_field(name="Clan War Rank",   value=f"`#{data.get('currentClanWarPosition','?')}`", inline=True)
    overview.add_field(name="Month Scores",    value=f"`{data.get('monthScores', 0):,}`",          inline=True)
    overview.add_field(name="All-Time Scores", value=f"`{data.get('allScores', 0):,}`",            inline=True)
    overview.set_footer(text=f"Data from api.kirka.io | Made by vlaims {get_egirl_suffix()}")
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
    view  = PaginationView(pages=pages, title=add_egirl_personality("🏰 Kiss Clan Members"), total_label=f"Total Members: {len(members)}")
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
        await interaction.followup.send(add_egirl_personality("❌ Could not fetch ranked 2v2 leaderboard from Kirka."))
        return
    results = data.get('results', [])
    season  = data.get('season')
    if not results:
        await interaction.followup.send(add_egirl_personality("The ranked 2v2 leaderboard is currently empty (no active season)."))
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
    title = add_egirl_personality(f"🏆 Global Ranked 2v2 Leaderboard" + (f" — Season {season}" if season else ""))
    view  = PaginationView(pages=pages, title=title)
    await interaction.followup.send(embed=view.create_embed(), view=view)


bot.run(os.environ.get('DISCORD_TOKEN'))