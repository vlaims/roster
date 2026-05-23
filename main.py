import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        
    async def setup_hook(self):
        # Your verified server ID remains active
        TEST_GUILD = discord.Object(id=841573598799593472) 
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)

bot = MyBot()

@bot.tree.command(name="members", description="Previews all registered data from the clan roster")
async def members(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://clan-bot--vlaims.replit.app/roster') as response:
                if response.status != 200:
                    await interaction.followup.send("❌ Error contacting the roster server.")
                    return
                data = await response.json()
                
        if not data:
            await interaction.followup.send("No registered members found in the roster.")
            return

        lines = []
        active_count = 0
        
        for index, item in enumerate(data, 1):
            # Mapping keys directly to your real website database schema fields
            player_name = item.get('player', item.get('name', 'Unknown'))
            player_id = item.get('id', '')
            discord_user = item.get('discord', 'N/A')
            status = str(item.get('status', 'ACTIVE')).upper()
            
            # Choose an emoji color indicator based on status
            status_emoji = "🟢" if status == "ACTIVE" else "🔴"
            if status == "ACTIVE":
                active_count += 1
            
            # Creates a beautifully formatted line for each clan mate
            id_bracket = f" (`{player_id}`)" if player_id else ""
            lines.append(f"{status_emoji} **{index}. {player_name}**{id_bracket} | Discord: `@{discord_user}`")
            
        member_list = "\n".join(lines)

        # Custom themed UI embed match to your dark mode dashboard look
        embed = discord.Embed(
            title="⚔️ Clan Roster Management Overview",
            url="https://clan-bot--vlaims.replit.app/roster",
            description=f"### Active Players: {active_count}/{len(data)}\n\n" + member_list[:3800],
            color=discord.Color.from_rgb(43, 45, 49) # Clean Discord dark dashboard gray
        )
        embed.set_footer(text="Data synced live from clan-bot--vlaims.replit.app")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send("❌ Failed to parse or fetch roster data from website.")

bot.run(os.environ.get('DISCORD_TOKEN'))
