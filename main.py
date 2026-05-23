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
    await interaction.response.defer()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://replit.app') as response:
                if response.status != 200:
                    await interaction.followup.send("❌ Error contacting the roster server.")
                    return
                data = await response.json()
                
        if not data:
            await interaction.followup.send("No registered members found in the roster.")
            return

        lines = []
        
        for index, item in enumerate(data, 1):
            # Mapping perfectly to your database schema fields from the image
            player_name = item.get('name', 'Unknown')
            discord_handle = item.get('discord_handle', 'N/A')
            player_id = item.get('player_id', '')
            
            # Formats each line: "👤 1. Ish (#37A3JS) | Discord: @4izennk"
            id_str = f" (`{player_id}`)" if player_id else ""
            lines.append(f"👤 **{index}. {player_name}**{id_str} | Discord: `@{discord_handle}`")
            
        member_list = "\n".join(lines)

        # Build clean embed profile layout
        embed = discord.Embed(
            title="📋 Clan Roster Database",
            url="https://replit.app",
            description=f"### Total Tracked Players: {len(data)}\n\n" + member_list[:3900],
            color=discord.Color.blue()
        )
        embed.set_footer(text="Live data synced from vlaims database")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error parsing data: {e}")
        await interaction.followup.send("❌ Failed to read database properties correctly.")

bot.run(os.environ.get('DISCORD_TOKEN'))
