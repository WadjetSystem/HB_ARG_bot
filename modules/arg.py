from disnake.ext import commands
from disnake import Interaction
import disnake
import aiohttp
import asyncio
import orjson
import hashlib
import io
import os
import re
import datetime
from lxml import html
from urllib.parse import urlparse, unquote
import tweepy

# clean text from html tags


def clean_text(string):
    string = string.replace("</h2>", "**\n\n")
    string = string.replace("<br>", "\n")
    string = string.replace("<p>", "")
    string = string.replace("</p>", "")
    string = string.replace("<h2>", "**")
    return string


class ARG(commands.Cog, name="ARG"):
    """ARG related functions"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.setup_bats_parser()
        self.setup_monitoring()
        self.setup_discord_channels()
        self.setup_pair_info()
        self.setup_balance()

        asyncio.ensure_future(self.monitor_bats())
        asyncio.ensure_future(self.monitor_balance_tweets())

    # setup functions

    def setup_bats_parser(self):
        # maybe we could try getting the key automatically from the document, or read it from a file
        self.decryptkey = {
            "yellowsnake": "I", "orangeturtle": "23", "whitedog": "6", "yellowmouse": "15", "redcat": "↗", "reddog": "51", "whiteelephant": ".-", "orangesnake": "J", "orangegiraffe": "H", "🙁": "T", "sadface": "T", "yellowelephant": "2", "bluepenguin": "U", "bluegiraffe": "F", "redmouse": "S", "bluerabbit": "H", "yellowcat": "O", "bluedog": "E", "redrabbit": "S", "blackdog": "E", "yellowrabbit": "R", "greenfrog": "←", "greenowl": "E", "👁️": "U", "eye": "U", "yellowbat": "P", "whiteturtle": "A", "bluecat": "I", "blackpenguin": "R", "whiteowl": "C", "blackturtle": "3", "redpenguin": "S", "bluesnake": "P", "redelephant": "K", "greengiraffe": "L", "blackrabbit": "M", "greenbat": "21", "upsidedownface": "L", "whitecat": "T", "whitebat": "L", "orangedog": "E", "greenelephant": "T", "yellowpenguin": "A", "orangefrog": "F", "blackcat": "M", "yellowdog": "...", "whitegiraffe": "N", "redfrog": "4", "whitepenguin": "♡", "yellowturtle": "Y", "yellowowl": "53", "💀": "A", "skull": "A", "orangeowl": "T", "redgiraffe": "111", "bluemouse": "-.-.", "greensnake": "↖", "blackfrog": "ZYXWVUTSRQPONMLKJIHGFEDCBA", "redowl": "→", "greenturtle": "R", "orangecat": "A", "🙂": "M", "happyface": "M", "orangeelephant": "N", "blacksnake": ".--.", "blueturtle": "♅", "orangebat": "1", "whitefrog": "41", "greenmouse": "C", "blackgiraffe": "5", "blackmouse": "↘", "greenrabbit": "4", "blueelephant": "A"
        }
        self.encryptkey = {y: x for x, y in self.decryptkey.items()}

        self.morsekey = {
            ".-": "A", "...": "S", "-.-.": "C", ".--.": "P"
        }

    def setup_monitoring(self):
        self.bats_url = "https://sunaiku-foundation.com/en/hiddenbats/"
        self.balance_tweets = [["Aine", 1526019608116969472, None, ":purple_circle:"],
                               ["Binato", 1526019606426488832, None, ":orange_circle:"]]
        self.filename = "hiddenbats"
        self.nonce = None

    def setup_discord_channels(self):
        self.bats_monitor_channels = orjson.loads(
            os.getenv('BATS_MONITOR_CHANNELS', '[]'))
        self.twitter_monitor_channels = orjson.loads(
            os.getenv('TWITTER_MONITOR_CHANNELS', '[]'))
        self.command_channels = orjson.loads(
            os.getenv('DISCORD_COMMAND_CHANNELS', '[]'))

    def setup_pair_info(self):
        self.pair_names = orjson.loads(
            os.getenv('PAIR_INFO', '[]')
        )
        self.first_tweet_date = orjson.loads(
            os.getenv('PAIR_FIRST_TWEET_DATE', '[]')
        )
        self.overwrite_name = os.getenv('TWEETER_OVERWRITE') # overwrites current tweeter if not None

    def setup_balance(self):
        # Authenticate to Twitter
        self.twitter_api = tweepy.Client(os.getenv('TWITTER_BEARER_CODE', ''))

    # helper functions

    # handle messages that may be longer than 2000 characters
    async def hb_send_message(self, interaction, message=None, files=[]):
        # if message is too long to be sent normally
        if len(message) > 2000:
            buffer = io.StringIO()
            buffer.write(message)
            buffer.seek(0)
            await interaction.response.send_message("Message is too long, uploading it as a file instead.", file=disnake.File(buffer, "message.txt"), ephemeral=self.is_not_in_whitelist(interaction.channel_id))
        else:
            await interaction.response.send_message(message, files=files, ephemeral=self.is_not_in_whitelist(interaction.channel_id))
        return

    # sending hidden bats HTML

    async def send_html_message(self, channels, prev_bytearray, current_bytearray, prev_nonce):
        text_prev = "Something changed in hiddenbats site. <:MizukiThumbsUp:925566710243803156>\n"
        text_new = str()
        if prev_nonce != self.nonce:
            text_prev += f"Previous nonce: {prev_nonce}\n"
            text_new = f"New nonce: {self.nonce}\n"
        text_prev += "Previous HTML:"
        text_new += "New HTML:"
        for channel in channels:
            async with channel.typing():
                await channel.send(text_prev, file=disnake.File(
                    prev_bytearray, filename=f'{self.filename}_old.html'))
                await channel.send(text_new, file=disnake.File(
                    current_bytearray, filename=f'{self.filename}_new.html'))
                # seek to start, otherwise the file won't send
                prev_bytearray.seek(0)
                current_bytearray.seek(0)

    # sending balance tweet alert

    def get_balance_tweet_message(self):

        for tweet_idx in range(0, len(self.balance_tweets)):

            tweet = self.twitter_api.get_tweet(
                self.balance_tweets[tweet_idx][1], tweet_fields=["public_metrics"])
            self.balance_tweets[tweet_idx][2] = tweet

        text = ""

        for tweet in self.balance_tweets:

            text += "Current status of {}**{}'s** tweet:\nLikes: {} -- RTs: {} -- QRTs: {}\n".format(
                tweet[3], tweet[0], tweet[2].data.public_metrics["like_count"], tweet[2].data.public_metrics["retweet_count"], tweet[2].data.public_metrics["quote_count"])

        tweeter1 = self.balance_tweets[0]
        tweeter2 = self.balance_tweets[1]
        tweet1 = tweeter1[2]
        tweet2 = tweeter2[2]
        likes1 = tweet1.data.public_metrics["like_count"]
        rts1 = tweet1.data.public_metrics["retweet_count"]
        qrts1 = tweet1.data.public_metrics["quote_count"]
        likes2 = tweet2.data.public_metrics["like_count"]
        rts2 = tweet2.data.public_metrics["retweet_count"]
        qrts2 = tweet2.data.public_metrics["quote_count"]
        diff_likes = abs(likes1 - likes2)
        diff_rts = abs(rts1 - rts2)
        diff_qrts = abs(qrts1 - qrts2)

        tweeter1_text = "{}**{}**".format(tweeter1[3], tweeter1[0])
        tweeter2_text = "{}**{}**".format(tweeter2[3], tweeter2[0])
        diff_likes_text = "**0**"
        diff_rts_text = "**0**"
        diff_qrts_text = "**0**"
        if diff_likes != 0:
            diff_likes_text = [
                tweeter1_text, tweeter2_text][likes2 > likes1] + " +" + str(diff_likes)
        if diff_rts != 0:
            diff_rts_text = [tweeter1_text,
                             tweeter2_text][rts2 > rts1] + " +" + str(diff_rts)
        if diff_qrts != 0:
            diff_qrts_text = [
                tweeter1_text, tweeter2_text][qrts2 > qrts1] + " +" + str(diff_qrts)

        text += "**Difference in Likes**: {}\n**Difference in RTs**: {}\n**Difference in QRTs**: {}".format(
            diff_likes_text, diff_rts_text, diff_qrts_text)
        if (diff_likes == "0") and (diff_rts == "0") and (diff_qrts == "0"):
            text += "\nPerfectly balanced. <:MizukiThumbsUp:925566710243803156>"
        return text

    async def send_balance_tweet_message(self, channels):

        text = self.get_balance_tweet_message()

        for channel in channels:
            async with channel.typing():
                await channel.send(text)

    # functions for Bats489 decryption and encryption. thanks to salty-dracon#8328 for the original code!

    def bats_values(self, inputstring):
        splitlist = inputstring.split(" ")
        combilist = []
        invalid = []
        for i in range(len(splitlist)):
            if splitlist[i].lower() in self.decryptkey:
                combilist.append(self.decryptkey[splitlist[i].lower()])
            else:
                combilist.append(":x:")
                invalid.append(splitlist[i].lower())
        bit = " | "
        joinedlist = bit.join(combilist)

        result = ""
        if len(combilist) == len(invalid):
            result += "No valid characters found."
        else:
            result += joinedlist
            if len(invalid) > 0:
                result += "\nInvalid characters: {}".format(", ".join(invalid))
        return result

    def bats_decrypt(self, inputstring):
        splitlist = inputstring.split(" ")
        combilist = []
        for i in range(len(splitlist)):
            if splitlist[i].lower() in self.decryptkey:
                combilist.append(self.decryptkey[splitlist[i].lower()])
        bit = ""
        joinedlist = bit.join(combilist)
        if len(joinedlist) == 0:
            return "No valid characters found."
        else:
            return joinedlist

    def bats_encrypt(self, inputstring):
        combilist = []
        for i in range(len(inputstring)):
            if inputstring[i].upper() in self.encryptkey:
                combilist.append(self.encryptkey[inputstring[i].upper()])
                combilist.append(" ")
        bit = ""
        joinedlist = bit.join(combilist)
        if len(joinedlist) == 0:
            return "No valid characters found."
        else:
            return joinedlist

    async def get_bats(self, session):
        async with session.get(self.bats_url) as r:
            if r.status == 200:
                data = await r.read()
                return data

    def is_not_in_whitelist(self, channel_id):
        return not channel_id in self.command_channels

    def response_to_byte_array(self, response_data):
        arr = io.BytesIO()
        arr.write(response_data)
        arr.seek(0)
        return arr

    def get_nonce(self, response):
        tree = html.fromstring(response)
        script = tree.xpath('/html/body/script[5]')[0].text
        try:
            return re.search("(?<='nonce': ')(.*)(?=',)", script)[0]
        except(TypeError):
            print('No nonce found.')
            return None

    # events

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author == self.bot.user:
            return

        if isinstance(message.channel, disnake.TextChannel):
            if not self.is_not_in_whitelist(message.channel.id):
                # this will work fine until they start retweeting each other's tweets
                if message.webhook_id:
                    if str(message.author) in ["Aine Ichirai/壱来アイネ#0000", "Binato Sotobara/卒斗原ビナト#0000"]:
                        if message.content.find('https://twitter.com/Aine_Ichirai/status/') != -1:
                            await message.add_reaction('<:MizukiThumbsUp:925566710243803156>')
                            return
                        elif message.content.find('https://twitter.com/Binato_Sotobara/status/') != -1:
                            await message.add_reaction('<:MizukiThumbsUp:925566710243803156>')
                            return

    # monitors hiddenbats site for any changes

    async def monitor_bats(self):
        response = ""
        prevHash = ""
        prevResponse = ""
        await self.bot.wait_until_ready()
        print('(bats) Starting bats monitoring.')
        channels = [self.bot.get_channel(channel)
                    for channel in self.bats_monitor_channels]
        # check if bot can actually access all monitor channels
        if None in channels:
            print('(bats) Failed to get info for a channel, retrying.')
            await asyncio.sleep(10)  # wait 10 seconds before trying again
            channels = [self.bot.get_channel(channel)
                        for channel in self.bats_monitor_channels]
            if None in channels:
                print('(bats) Failed to get info for a channel.')
                channels = list(filter(None, channels))
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # perform the get request and store it in a var
                    response = await self.get_bats(session)
                    currentHash = hashlib.sha1(response).hexdigest()
                    # check if new hash is same as the previous hash
                    if prevHash != currentHash:
                        if len(prevHash) != 0:
                            prev_nonce = self.nonce
                            self.nonce = self.get_nonce(response)
                            prev_bytearray = self.response_to_byte_array(
                                prevResponse)
                            current_bytearray = self.response_to_byte_array(
                                response)
                            # notify about changes
                            await self.send_html_message(
                                channels, prev_bytearray, current_bytearray, prev_nonce)
                        else:
                            self.nonce = self.get_nonce(response)
                        prevHash = currentHash
                        prevResponse = response
                    # wait for 30 seconds
                    await asyncio.sleep(30)
                # handle exceptions
                except Exception as e:
                    print("Error", e)
                    for channel in channels:
                        channel.send(
                            'An error happened, please report it to the bot creator kthx:', e)

    # monitors balance tweets

    async def monitor_balance_tweets(self):
        await self.bot.wait_until_ready()
        print('(balance) Starting balance tweets monitoring.')
        channels = [self.bot.get_channel(channel)
                    for channel in self.twitter_monitor_channels]
        # check if bot can actually access all monitor channels
        if None in channels:
            print('(balance) Failed to get info for a channel, retrying.')
            await asyncio.sleep(10)  # wait 10 seconds before trying again
            channels = [self.bot.get_channel(channel)
                        for channel in self.twitter_monitor_channels]
            if None in channels:
                print('(balance) Failed to get info for a channel.')
                channels = list(filter(None, channels))
        while True:
            try:
                await self.send_balance_tweet_message(channels)
                # wait for 30 minutes
                await asyncio.sleep(1800)
            # handle exceptions
            except Exception as e:
                print("Error", e)
                for channel in channels:
                    channel.send(
                        'An error happened, please report it to the bot creator kthx:', e)

    # slash commands

    @commands.slash_command(
        name="password", description='Tries the password on the hiddenbats site.'
    )
    async def password(self, interaction=Interaction, *, password: str = commands.Param(description="a Nirvana Spell, e.g. PAN"), language: str = commands.Param(default=0, description="Language to use", choices=["English", "Japanese"])):
        if self.nonce == None:
            await interaction.response.send_message("Nonce is missing. Please wait a bit or contact the bot's creator if this persists.", ephemeral=self.is_not_in_whitelist(interaction.channel_id))
            return
        form_data = aiohttp.FormData()
        form_data.add_field("action", "hiddenbats_password_check")
        form_data.add_field("nonce", self.nonce)
        form_data.add_field("password", password)
        if language == 'Japanese':
            url = "https://sunaiku-foundation.com/wp-admin/admin-ajax.php"
        else:
            url = "https://sunaiku-foundation.com/en/wp-admin/admin-ajax.php"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data) as r:
                if r.status == 200:
                    data = await r.text()
                    text = orjson.loads(data)
                    if text["state"] == "correct":
                        await self.hb_send_message(interaction, message=clean_text(text["html"]))
                    elif text["state"] == "failed":
                        await self.hb_send_message(interaction, message='Wrong password.')
                    else:
                        await self.hb_send_message(interaction, message=f'Unknown state {text["state"]}.')
        return

    @commands.slash_command(
        name="values", description="Displays values for a Bats489 encrypted string."
    )
    async def values(self, interaction=Interaction, *, string: str = commands.Param(description="String to decrypt, e.g. bluesnake yellowpenguin whitegiraffe.")):
        await self.hb_send_message(interaction, message=self.bats_values(string))
        return

    @commands.slash_command(
        name="decrypt", description="Fully decrypts a Bats489 encrypted string."
    )
    async def decrypt(self, interaction=Interaction, *, string: str = commands.Param(description="String to decrypt, e.g. bluesnake yellowpenguin whitegiraffe.")):
        await self.hb_send_message(interaction, message=self.bats_decrypt(string))
        return

    @commands.slash_command(
        name="encrypt", description="Encrypts a string with Bats489."
    )
    async def encrypt(self, interaction=Interaction, *, string: str = commands.Param(description="String to encrypt, e.g. PAN.")):
        await self.hb_send_message(interaction, message=self.bats_encrypt(string))
        return

    @commands.slash_command(
        name="balance", description="Retrieve Balance Experiment status."
    )
    async def balance(self, interaction=Interaction):
        await self.hb_send_message(interaction, self.get_balance_tweet_message())
        return

    @commands.slash_command(
        name="thumbsup", description="you have 21 minutes to get help"
    )
    async def thumbsup(self, interaction=Interaction):
        await self.hb_send_message(interaction, message="<:MizukiThumbsUp:925566710243803156>")
        return

    @commands.slash_command(
        name="media", description="Mirrors the specified picture/video from the Sunaiku Foundation website."
    )
    async def media(self, interaction=Interaction, *, url: str = commands.Param(description="a Sunaiku Foundation media URL")):
        if not url.startswith("https://sunaiku-foundation.com"):
            await self.hb_send_message(interaction, message="Not a valid Sunaiku Foundation URL.")
            return
        filename = os.path.basename(unquote(urlparse(url).path))
        _, extension = os.path.splitext(filename)
        if not extension in [".png", ".jpg", ".jpeg", ".webm", ".mp4"]:
            await self.hb_send_message(interaction, message="Not a valid picture/video URL.")
            return
        await interaction.response.defer(ephemeral=self.is_not_in_whitelist(interaction.channel_id))
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'referer': 'https://sunaiku-foundation.com/'}) as resp:
                buffer = io.BytesIO(await resp.read())
        if resp.status == 200:
            await interaction.followup.send(file=disnake.File(buffer, filename=filename), ephemeral=self.is_not_in_whitelist(interaction.channel_id))
        elif resp.status == 403:
            await interaction.followup.send("Unauthorized, cannot access image.", ephemeral=self.is_not_in_whitelist(interaction.channel_id))
        elif resp.status == 404:
            await interaction.followup.send("Image not found.", ephemeral=self.is_not_in_whitelist(interaction.channel_id))
        else:
            await interaction.followup.send(f"Failed. Unknown response code: {resp.status}. Please contact the bot's creator kthx.")
        return

    @commands.slash_command(
        name="time", description="Posts how much time is left until the next tweet."
    )
    async def time(self, interaction=Interaction):
        todays_date = datetime.datetime.now(datetime.timezone.utc)
        todays_tweet_post_date = todays_date.replace(hour=2, minute=00)
        tomorrows_tweet_post_date = todays_tweet_post_date + \
            datetime.timedelta(days=1)
        first_tweet_date = datetime.datetime(
            self.first_tweet_date[0], self.first_tweet_date[1], self.first_tweet_date[2], hour=2, tzinfo=datetime.timezone.utc)
        if todays_date.time() < datetime.time(2, 00):
            unix_timestamp = datetime.datetime.timestamp(
                todays_tweet_post_date)
        else:
            unix_timestamp = datetime.datetime.timestamp(
                tomorrows_tweet_post_date)
        if (todays_date - first_tweet_date).days % 2 == 0:
            tweet_sender = self.pair_names[1]
        else:
            tweet_sender = self.pair_names[0]

        # overwrite name in case of special circumstances
        if self.overwrite_name != None:
            tweet_sender = self.overwrite_name

        await self.hb_send_message(interaction, message=f"Next tweet will happen <t:{str(unix_timestamp)[:10]}:R> and it'll be tweeted by {tweet_sender}.")
        return


def setup(bot: commands.Bot):
    bot.add_cog(ARG(bot))
