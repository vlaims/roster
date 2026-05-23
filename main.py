import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        
    async def setup_hook(self):
        TEST_GUILD = discord.Object(id=841573598799593472) 
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)

bot = MyBot()

@bot.tree.command(name="members", description="Previews all registered data from the Supabase clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    
    # Grab keys from Railway Variables securely
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        await interaction.followup.send("❌ Error: Supabase credentials are missing in Railway Environment Variables.")
        return

    # Direct Supabase API query link
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
            lines.append(f"⚡ **{index}. {player_name}**{id_bracket} | Discord: `@{discord_user}`")
            
        member_list = "\n".join(lines)

        embed = discord.Embed(
            title="⚡ Live Supabase Clan Roster",
            description=f"### Total Tracked Players: {len(lines)}\n\n" + member_list[:3900],
            color=discord.Color.from_rgb(63, 207, 142) # Supabase branding green icon color
        )
        embed.set_footer(text="Cloud database active | 24/7 Sync")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"SUPABASE FETCH ERROR: {e}")
        await interaction.followup.send("❌ Failed to parse data from your Supabase cloud repository.")

bot.run(os.environ.get('DISCORD_TOKEN'))
