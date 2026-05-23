import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        
    async def setup_hook(self):
        # Your target guild sync configuration
        TEST_GUILD = discord.Object(id=841573598799593472) 
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)

bot = MyBot()

@bot.tree.command(name="members", description="Previews all registered data from the clan roster")
async def members(interaction: discord.Interaction):
    # Extends the interaction life to bypass a standard 3-second timeout limit
    await interaction.response.defer()
    
    try:
        # Give your Replit backend up to 10 seconds to compile response packets
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Connect directly to your web app path
            async with session.get('https://clan-bot--vlaims.replit.app/roster') as response:
                if response.status != 200:
                    await interaction.followup.send(f"❌ Error contacting the roster app. (Server Status: `{response.status}`)")
                    return
                data = await response.json()
                
        if not data:
            await interaction.followup.send("No registered members found in the roster database.")
            return

        lines = []
        for index, item in enumerate(data, 1):
            if not isinstance(item, dict):
                continue
                
            # Mapping columns explicitly matching your real schema image layout
            player_name = item.get('name', 'Unknown')
            discord_user = item.get('discord_handle', 'N/A')
            player_id = item.get('player_id', '')
            
            # Formats clean rows: "👤 1. Ish (#37A3JS) | Discord: @4izennk"
            id_bracket = f" (`{player_id}`)" if player_id else ""
            lines.append(f"👤 **{index}. {player_name}**{id_bracket} | Discord: `@{discord_user}`")
            
        member_list = "\n".join(lines)

        # Renders the clean aesthetic embed
        embed = discord.Embed(
            title="📋 Clan Roster Database Overview",
            url="https://clan-bot--vlaims.replit.app/roster",
            description=f"### Total Tracked Players: {len(lines)}\n\n" + member_list[:3900],
            color=discord.Color.blue()
        )
        embed.set_footer(text="Live data matched from vlaims server database")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"DATABASE DESERIALIZATION ERROR: {e}")
        await interaction.followup.send(f"❌ Failed to parse data layout structure.")

bot.run(os.environ.get('DISCORD_TOKEN'))
