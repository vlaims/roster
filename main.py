import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

# 🎨 HELPER FUNCTION: Maps standard characters to a Fancy Bold Serif Font Style
def to_fancy_font(text):
    normal_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy_chars  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    trans = str.maketrans(normal_chars, fancy_chars)
    return str(text).translate(trans)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        
    async def setup_hook(self):
        TEST_GUILD = discord.Object(id=841573598799593472) 
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)

bot = MyBot()

# ----------------------------------------------------
# COMMAND 1: THE LIVE ROSTER LOOKUP
# ----------------------------------------------------
@bot.tree.command(name="members", description="Previews all registered data from the Supabase clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        await interaction.followup.send("❌ Error: Supabase credentials are missing in Railway Environment Variables.")
        return

    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?select=*"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(target_endpoint, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send(f"❌ Error communicating with Supabase database. (Code: `{response.status}`)")
                    return
                data = await response.json()
                
        if not data:
            await interaction.followup.send("📂 Connection successful! However, your Supabase `roster` table is currently empty.")
            return

        lines = []
        for index, item in enumerate(data, 1):
            if not isinstance(item, dict): continue
            
            raw_name = item.get('name', 'Unknown')
            discord_user = item.get('discord_handle', 'N/A')
            player_id = item.get('player_id', 'N/A')
            fancy_name = to_fancy_font(raw_name)
            
            lines.append(f"👤 **{index}. {fancy_name}**\n- # ↳ *ID:* `{player_id}` • *Discord:* `@{discord_user}`")
            
        member_list = "\n".join(lines)

        embed = discord.Embed(
            title="Kiss Clan",
            description=f"### Total Tracked Players: {len(lines)}\n\n" + member_list[:3900],
            color=discord.Color.from_rgb(63, 207, 142)
        )
        embed.set_footer(text="Made by vlaims")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"SUPABASE FETCH ERROR: {e}")
        await interaction.followup.send("Failed to parse data from your Supabase cloud repository.")

# ----------------------------------------------------
# COMMAND 2: THE SECURE /REGISTER COMMAND
# ----------------------------------------------------
@bot.tree.command(name="register", description="Register yourself or a clan member to the Supabase roster database")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    name="The player's clan nickname or gaming name",
    player_id="The player's unique in-game identification ID tag"
)
async def register(interaction: discord.Interaction, name: str, player_id: str):
    await interaction.response.defer()
    
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        await interaction.followup.send("❌ Error: Supabase credentials are missing in Railway Environment Variables.")
        return

    discord_handle = interaction.user.name
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    payload = {
        "name": name,
        "discord_handle": discord_handle,
        "player_id": player_id
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(target_endpoint, headers=headers, json=payload) as response:
                if response.status in [200, 201]:
                    fancy_conf_name = to_fancy_font(name)
                    
                    embed = discord.Embed(
                        title="Registration Successful!",
                        description=f"Welcome to the roster database, **{fancy_conf_name}**!",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Name", value=f"`{name}`", inline=True)
                    embed.add_field(name="Game Account ID", value=f"`{player_id}`", inline=True)
                    embed.add_field(name="Discord Username", value=f"`@{discord_handle}`", inline=False)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Failed writing row to database. (HTTP Error: `{response.status}`)")
                    
    except Exception as e:
        await interaction.followup.send("❌ Critical network failure occurred attempting cloud updates.")

# ----------------------------------------------------
# COMMAND 3: THE BRAND NEW /KICK COMMAND
# ----------------------------------------------------
@bot.tree.command(name="kick", description="Remove a player from the Supabase roster database")
@app_commands.default_permissions(administrator=True) # Locked to admins only
@app_commands.describe(
    name="The exact name of the player you want to remove from the roster"
)
async def kick(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        await interaction.followup.send("❌ Error: Supabase credentials are missing in Railway Environment Variables.")
        return

    # Targeting the row by filtering where 'name' matches what the admin types
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster?name=eq.{name}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Prefer": "return=representation" # This lets us confirm if a row was actually deleted
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Send an HTTP DELETE request to Supabase to remove the row
            async with session.delete(target_endpoint, headers=headers) as response:
                print(f"DEBUG KICK: Delete status received: {response.status}")
                
                if response.status == 200:
                    deleted_data = await response.json()
                    
                    # If Supabase returns an empty list, it means the player wasn't in the database
                    if not deleted_data:
                        await interaction.followup.send(f"⚠️ Could not find a player named `{name}` in the database.")
                        return
                    
                    fancy_kicked_name = to_fancy_font(name)
                    
                    embed = discord.Embed(
                        title="Player Removed",
                        description=f"**{fancy_kicked_name}** has been successfully scrubbed from the clan database roster.",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text="Supabase Cloud synchronized.")
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Failed to delete player. (HTTP Error: `{response.status}`)")
                    
    except Exception as e:
        print(f"CRITICAL KICK FAILURE: {e}")
        await interaction.followup.send("❌ Critical network failure occurred attempting cloud deletion.")

bot.run(os.environ.get('DISCORD_TOKEN'))
