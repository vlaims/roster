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

@bot.tree.command(name="members", description="Previews all registered data from the clan roster")
async def members(interaction: discord.Interaction):
    # This gives us a 15-minute window so Discord doesn't say "Interaction Failed"
    await interaction.response.defer()
    
    try:
        # Give the Replit server 10 seconds to respond before giving up
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('https://replit.app') as response:
                print(f"DEBUG: Connected to API. Status code received: {response.status}")
                
                if response.status != 200:
                    await interaction.followup.send(f"❌ Web server returned an error code: `{response.status}`")
                    return
                    
                raw_data = await response.json()
                
        # 🚨 PRINT THE RAW DATA TO RAILWAY LOGS SO WE CAN INSPECT IT
        print(f"DEBUG RAW PAYLOAD: {raw_data}")
                
        if isinstance(raw_data, dict):
            if 'data' in raw_data: data = raw_data['data']
            elif 'roster' in raw_data: data = raw_data['roster']
            else: data = next((v for v in raw_data.values() if isinstance(v, list)), [])
        else:
            data = raw_data
            
        if not data or not isinstance(data, list):
            await interaction.followup.send("⚠️ Database successfully read, but the roster table is completely empty.")
            return

        lines = []
        for index, item in enumerate(data, 1):
            if not isinstance(item, dict): continue
            
            player_name = item.get('name') or item.get('player') or 'Unknown'
            discord_handle = item.get('discord_handle') or item.get('discord') or 'N/A'
            player_id = item.get('player_id') or item.get('id') or ''
            
            id_str = f" (`{player_id}`)" if player_id else ""
            lines.append(f"👤 **{index}. {player_name}**{id_str} | Discord: `@{discord_handle}`")
            
        member_list = "\n".join(lines)

        embed = discord.Embed(
            title="📋 Clan Roster Database",
            url="https://replit.app",
            description=f"### Total Tracked Players: {len(lines)}\n\n" + member_list[:3900],
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
        
    except aiohttp.ClientConnectorError:
        await interaction.followup.send("❌ Could not connect to Replit. Check if your Replit app is awake or asleep!")
    except Exception as e:
        print(f"CRITICAL PARSE ERROR: {e}")
        await interaction.followup.send(f"❌ Processing layout failed. Error trace: `{str(e)}`")

bot.run(os.environ.get('DISCORD_TOKEN'))
