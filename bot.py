import disnake
from disnake.ext import commands
import os

# if you want to run without heroku. could probably improve this check by checking an env only in heroku or something
local_testing = False
if local_testing:
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
    await bot.change_presence(
        activity=disnake.Activity(
            type=disnake.ActivityType.playing, name="Zero Time Dilemma 🐌")
    )


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, disnake.ext.commands.errors.MissingRequiredArgument):
        print('Exception:', error)
        await ctx.send("Parameter missing.")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
