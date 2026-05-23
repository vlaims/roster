import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        
    async def setup_hook(self):
        # Your target guild sync configuration remains locked in
        TEST_GUILD = discord.Object(id=841573598799593472) 
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)

bot = MyBot()

# ----------------------------------------------------
# COMMAND 1: THE EXISTING /MEMBERS COMMAND
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
            
            player_name = item.get('name', 'Unknown')
            discord_user = item.get('discord_handle', 'N/A')
            player_id = item.get('player_id', '')
            
            id_bracket = f" (`{player_id}`)" if player_id else ""
            lines.append(f"💋 **{index}. {player_name}**{id_bracket} | Discord: `@{discord_user}`")
            
        member_list = "\n".join(lines)

        embed = discord.Embed(
            title="💋 Kiss clan",
            description=f"### Total Tracked Players: {len(lines)}\n\n" + member_list[:3900],
            color=discord.Color.from_rgb(63, 207, 142)
        )
        embed.set_footer(text="Kissbase 💋 | 24/7 Sync")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"SUPABASE FETCH ERROR: {e}")
        await interaction.followup.send("❌ Failed to parse data from your Supabase cloud repository.")

# ----------------------------------------------------
# COMMAND 2: THE BRAND NEW /REGISTER COMMAND
# ----------------------------------------------------
@bot.tree.command(name="register", description="Register yourself or a clan member to the Supabase roster database")
@app_commands.describe(
    name="The player's clan nickname or gaming name",
    player_id="The player's unique in-game identification ID tag"
)
async def register(interaction: discord.Interaction, name: str, player_id: str):
    # Defer response to avoid 3-second timeout windows
    await interaction.response.defer()
    
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        await interaction.followup.send("❌ Error: Supabase credentials are missing in Railway Environment Variables.")
        return

    # Automatically grab the user's current Discord username handle (e.g., '4izennk')
    discord_handle = interaction.user.name

    # Setup database target endpoints
    target_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/roster"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal" # Optimization payload rule
    }

    # Data structure matching your exact Supabase column headers
    payload = {
        "name": name,
        "discord_handle": discord_handle,
        "player_id": player_id
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # We use an HTTP POST request to append rows to your Supabase grid table
            async with session.post(target_endpoint, headers=headers, json=payload) as response:
                print(f"DEBUG REGISTER: Post status received: {response.status}")
                
                # Supabase responds with 201 Created when a database write succeeds
                if response.status in [200, 201]:
                    # Create a confirmation embed layout design
                    embed = discord.Embed(
                        title="✅ Registration Successful!",
                        description=f"Welcome to the roster database, **{name}**!",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="👤 Character Name", value=f"`{name}`", inline=True)
                    embed.add_field(name="🆔 Game Account ID", value=f"`{player_id}`", inline=True)
                    embed.add_field(name="💬 Discord Profile", value=f"`@{discord_handle}`", inline=False)
                    embed.set_footer(text="Data added straight to Supabase cloud logs.")
                    
                    await interaction.followup.send(embed=embed)
                else:
                    error_text = await response.text()
                    print(f"DATABASE POST ERROR BACKEND: {error_text}")
                    await interaction.followup.send(f"❌ Failed writing row to database. (HTTP Error: `{response.status}`)")
                    
    except Exception as e:
        print(f"CRITICAL WRITE REGISTRATION FAILURE: {e}")
        await interaction.followup.send("❌ Critical network failure occurred attempting cloud updates.")

bot.run(os.environ.get('DISCORD_TOKEN'))
