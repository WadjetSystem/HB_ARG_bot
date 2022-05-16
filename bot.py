import disnake
from disnake.ext import commands
import os

# checks if it's running in heroku
if not os.getenv("HEROKU"):
    print('Starting in local mode.')
    from dotenv import load_dotenv
    load_dotenv()
intents = disnake.Intents().default()
intents.message_content = True
# prefix our commands with '🦇', even though we don't have any
bot = commands.Bot(command_prefix='🦇', help_command=None, intents=intents)
bot.load_extension("modules.arg")


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, disnake.ext.commands.errors.MissingRequiredArgument):
        print('Exception:', error)
        await ctx.send("Parameter missing.")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
