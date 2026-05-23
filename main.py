import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        
    async def setup_hook(self):
        # Syncs commands globally so they appear on Discord
        await self.tree.sync()

bot = MyBot()

@bot.tree.command(name="members", description="Previews all registered data from the clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://clan-bot--vlaims.replit.app/') as response:
                if response.status != 200:
                    await interaction.followup.send("❌ Error contacting the roster server.")
                    return
                data = await response.json()
                
        if not data:
            await interaction.followup.send("No registered members found in the roster.")
            return

        lines = []
        for index, item in enumerate(data, 1):
            name = item.get('name', 'Unknown')
            role = item.get('role', 'Member')
            lines.append(f"**{index}. {name}** - {role}")
            
        member_list = "\n".join(lines)

        embed = discord.Embed(
            title="📋 Registered Clan Roster",
            url="https://clan-bot--vlaims.replit.app/",
            description=member_list[:4096],
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send("❌ Failed to fetch roster data.")

# Railway automatically passes your secret token here via environment variables
bot.run(os.environ.get('DISCORD_TOKEN'))