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
import time
from lxml import html
from urllib.parse import urlparse, unquote
import tweepy
import random

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

        self.setup_maintenance()
        self.setup_bats_parser()
        self.setup_monitoring()
        self.setup_discord_channels()
        self.setup_pair_info()
        # self.setup_balance()
        self.setup_activity()

        asyncio.ensure_future(self.monitor_bats())
        # asyncio.ensure_future(self.monitor_balance())
        asyncio.ensure_future(self.update_activity())

    # setup functions

    def setup_maintenance(self):
        self.staff_roles = orjson.loads(
            os.getenv('STAFF_ROLES', '[]'))
        self.admin_users = orjson.loads(
            os.getenv('ADMIN_USERS', '[]'))

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
        self.balance_accounts = [["Mariha", 1526728623511969792, None, ":anger:"],
                                 ["Lumina", 1526731623987019776, None, ":green_book:"]]
        self.balance_polls = [["Iris", 1536891506124267520, None, "<:SchrodIris:669779611374190623>"],
                              ["Kairo", 1536891506124267520, None, ":broom:"]]
        self.monitor_messages = ["Something changed in hiddenbats site. <:MizukiThumbsUp:925566710243803156>\n", "There has been a change in the website known as the Hidden Bats from the SUNAIKU FOUNDATION. <:TesaThumbsUp:669779611294498816>\n",
                                 "A modification has been detected in the SUNAIKU FOUNDATION's Hidden Bats webpage. <a:aiba_hack:633702989361840138>\n", "Changes have been found in the webpage with the hidden bats, brought to you by the SUNAIKU FOUNDATION. <:paiaww:920558287248830474>\n", "hiddenbats is change <:TesaToo:595343260428271655>\n", "CHANGE <:TesaWoah:920563525443788840>\n"]
        self.filename = "hiddenbats"
        self.nonce = None
        self.monitor_all = True

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
        # overwrites current tweeter if not blank
        self.overwrite_name = os.getenv('TWEETER_OVERWRITE', "")
        # for example: ["Mariha Monzen/門前マリハ • TweetShift#0000", "Lumina Rikujo/離久浄ルミナ • TweetShift#0000"]
        self.current_tweeters = orjson.loads(
            os.getenv('CURRENT_TWEETERS', '[]'))

    def setup_balance(self):
        # Authenticate to Twitter
        self.twitter_api = tweepy.Client(os.getenv('TWITTER_BEARER_CODE', ''))
        self.balance_delay = 600  # by default, 10 minutes, but can be changed later

    def setup_activity(self):
        self.activities = [(disnake.ActivityType.playing, "ShovelForge ⛏"), (disnake.ActivityType.playing, "Zero Time Dilemma 🐌"), (disnake.ActivityType.playing, "World's End Club 🚚☄️"), (disnake.ActivityType.playing, "999 🧊"),
                           (disnake.ActivityType.playing, "AI: THE SOMNIUM FILES 👁️"), (disnake.ActivityType.playing,
                                                                                        "Never7 🔔"), (disnake.ActivityType.playing, "Virtue's Last Reward 🆎"),
                           (disnake.ActivityType.playing, "Danganronpa 🙄"), (disnake.ActivityType.playing, "NirvanA Initiative 🦇"),  (disnake.ActivityType.playing, "The Centennial Case 🥜"), (disnake.ActivityType.playing, "428 Shibuya Scramble 🍌"), (disnake.ActivityType.watching, "Danganronpa 3 💀"), (disnake.ActivityType.playing, "Ever17 🐹"), (disnake.ActivityType.playing, "Remember11 🍼"), (disnake.ActivityType.playing, "Collar × Malice 🐈")]

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

# verifies if the user has staff perms
    def verify_permissions(self, interaction):
        if interaction.user.id in self.admin_users:
            return True
        for role in self.staff_roles:
            if interaction.user.get_role(role) != None:
                return True
        return False

    # sending hidden bats HTML

    async def send_html_message(self, channels, prev_bytearray, current_bytearray, prev_nonce):
        text_prev = random.choice(self.monitor_messages)
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
            text += f"Current status of {tweet[3]}**{tweet[0]}'s** tweet:\nLikes: {tweet[2].data.public_metrics['like_count']} -- RTs: {tweet[2].data.public_metrics['retweet_count']} -- QRTs: {tweet[2].data.public_metrics['quote_count']}\n"
        tweeter_data = list()
        for tweeter in self.balance_tweets:
            tweet = tweeter[2]
            likes = tweet.data.public_metrics["like_count"]
            rts = tweet.data.public_metrics["retweet_count"]
            qrts = tweet.data.public_metrics["quote_count"]
            tweeter_data.append((likes, rts, qrts))
        diff_list = list()  # likes, rts, qrts, like+rts, all
        for i in range(3):
            diff_list.append(tweeter_data[0][i] - tweeter_data[1][i])
        diff_list.append(diff_list[0] + diff_list[1])  # like + rts
        diff_list.append(diff_list[2] + diff_list[3])  # all
        # aine
        tweeter1_text = f"{self.balance_tweets[0][3]}**{self.balance_tweets[0][0]}**"
        # binato
        tweeter2_text = f"{self.balance_tweets[1][3]}**{self.balance_tweets[1][0]}**"
        # diff likes, diff retweets, diff qrts, diff like+rts and diff all
        diff_text_list = ["**0**" for x in range(0, 5)]
        for i in range(len(diff_list)):
            if diff_list[i] != 0:
                diff_text_list[
                    i] = f"{[tweeter1_text, tweeter2_text][diff_list[i] < 0]} +{abs(diff_list[i])}"
        text += f"**Difference in Likes**: {diff_text_list[0]}\n**Difference in RTs**: {diff_text_list[1]}\n**Difference in QRTs**: {diff_text_list[2]}\n**Total difference**: {diff_text_list[4]}"
        if (diff_list[0] == 0) and (diff_list[1] == 0) and (diff_list[2] == 0):
            text += "\nPerfectly balanced. <:MizukiThumbsUp:925566710243803156>"
        return text

    async def send_balance_tweet_message(self, channels):
        text = self.get_balance_tweet_message()
        for channel in channels:
            async with channel.typing():
                await channel.send(text)
        return

    # sending balance followers alert

    def get_balance_followers_message(self):
        for account_idx in range(0, len(self.balance_accounts)):
            account = self.twitter_api.get_user(
                id=self.balance_accounts[account_idx][1], user_fields=["public_metrics"])
            self.balance_accounts[account_idx][2] = account
        text = ""
        for account in self.balance_accounts:
            text += f"Current followers of {account[3]}**{account[0]}**: {account[2].data.public_metrics['followers_count']}\n"
        account_data = list()
        for account in self.balance_accounts:
            status = account[2]
            followers = status.data.public_metrics["followers_count"]
            account_data.append((followers,))
        follower_diff = account_data[0][0] - account_data[1][0]
        # account 1
        account1_text = f"{self.balance_accounts[0][3]}**{self.balance_accounts[0][0]}**"
        # account 2
        account2_text = f"{self.balance_accounts[1][3]}**{self.balance_accounts[1][0]}**"
        # diff accounts
        diff_text = "**0**"
        if follower_diff != 0:
            diff_text = f"{[account1_text, account2_text][follower_diff < 0]} +{abs(follower_diff)}"
        text += f"**Difference in Followers**: {diff_text}"
        if (follower_diff == 0):
            text += "\nPerfectly balanced. <:MizukiThumbsUp:925566710243803156>"
        return text

    async def send_balance_followers_message(self, channels):
        text = self.get_balance_followers_message()
        for channel in channels:
            async with channel.typing():
                await channel.send(text)
        return

    # sending balance poll alert

    def get_balance_poll_message(self):

        tweet = self.twitter_api.get_tweet(
            self.balance_polls[0][1], tweet_fields=["public_metrics"], expansions=["attachments.poll_ids"])
        poll = tweet.includes["polls"][0]
        self.balance_polls[0][2] = poll.options[0]
        self.balance_polls[1][2] = poll.options[1]

        text = ""
        text += "Current poll status:\n"
        vote_data = list()
        for account in self.balance_polls:
            status = account[2]
            votes = status["votes"]
            vote_data.append(votes)
        vote_diff = vote_data[0] - vote_data[1]
        # account 1
        account1_text = f"{self.balance_polls[0][3]}**{self.balance_polls[0][0]}**"
        # account 2
        account2_text = f"{self.balance_polls[1][3]}**{self.balance_polls[1][0]}**"
        text += f"{account1_text}: {vote_data[0]}\n"
        text += f"{account2_text}: {vote_data[1]}\n"
        # diff votes
        diff = vote_diff
        diff_text = "**0**"
        if diff != 0:
            diff_text = f"{[account1_text, account2_text][diff < 0]} +{abs(diff)}"
        text += f"**Difference**: {diff_text}"
        if (diff == 0):
            text += "\nPerfectly balanced. <:MizukiThumbsUp:925566710243803156>"
        return text

    async def send_balance_poll_message(self, channels):
        text = self.get_balance_poll_message()
        for channel in channels:
            async with channel.typing():
                await channel.send(text)
        return

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
        try:
            async with session.get(self.bats_url) as r:
                if r.status == 200:
                    data = await r.read()
                    return data
        except Exception as e:
            print('An error occured while getting bats info -', e)
            return None

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

    @ commands.Cog.listener()
    async def on_message(self, message):

        if message.author == self.bot.user:
            return

        if isinstance(message.channel, disnake.TextChannel):
            if not self.is_not_in_whitelist(message.channel.id):
                # this will work fine until they start retweeting each other's tweets
                if message.webhook_id:
                    if str(message.author) in self.current_tweeters:
                        if message.content.find('https://twitter.com/') != -1:
                            await message.add_reaction('<:MizukiThumbsUp:925566710243803156>')
                        if "iris" in str(message.author).lower():
                            await self.bot.change_presence(activity=disnake.Activity(
                                type=self.activities[0][0], name=self.activities[0][1]))  # shovelforge
                        return
                else:
                    lowered_string = message.content.lower()
                    if lowered_string == "we're no strangers to love":
                        await message.channel.send('you know the rules and so do AI')
                    if lowered_string.find('erotic') != -1:
                        await message.add_reaction('💢')
                    # tax evasion is a crime
                    if lowered_string.find('tax eva') != -1:
                        await message.add_reaction('📗')
                    if lowered_string.find('#kairosweep') != -1:
                        await message.add_reaction('🧹')
                    if lowered_string.find('#taithevote') != -1:
                        await message.add_reaction('⚖️')
                    if lowered_string.find('#irissweep') != -1:
                        await message.add_reaction('<:Tesoul:669779611336310784>')
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
                    if response == None:
                        continue
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
                            if (prev_nonce != self.nonce) or self.monitor_all:
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

    # monitors balance experiment

    async def monitor_balance(self):
        await self.bot.wait_until_ready()
        print('(balance) Starting balance experiment monitoring.')
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
                # await self.send_balance_tweet_message(channels)
                await self.send_balance_poll_message(channels)
                # wait for 10 minutes
                current_time = time.time()
                while current_time + self.balance_delay > time.time():
                    await asyncio.sleep(1)

            # handle exceptions
            except Exception as e:
                print("Error", e)
                for channel in channels:
                    channel.send(
                        'An error happened, please report it to the bot creator kthx:', e)

    # changes activity randomly every 30 minutes

    async def update_activity(self):
        await self.bot.wait_until_ready()
        while True:
            random_activity = random.choice(self.activities)
            await self.bot.change_presence(
                activity=disnake.Activity(
                    type=random_activity[0], name=random_activity[1]))
            await asyncio.sleep(1800)  # wait 30 minutes

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

    """ Balance experiments over.
    @commands.slash_command(
        name="balance", description="STAFF ONLY - Retrieve Balance Experiment status."
    )
    async def balance(self, interaction=Interaction):
        if self.verify_permissions(interaction):
            # await self.hb_send_message(interaction, self.get_balance_tweet_message())
            # await self.hb_send_message(interaction, self.get_balance_followers_message())
            await self.hb_send_message(interaction, self.get_balance_poll_message())
        else:
            await interaction.response.send_message("You're not staff.", ephemeral=True)
        return
    """

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
        if len(self.overwrite_name) > 0:
            tweet_sender = self.overwrite_name

        await self.hb_send_message(interaction, message=f"Next tweet will happen <t:{str(unix_timestamp)[:10]}:R> and it'll be tweeted by {tweet_sender}.")
        return

    @commands.slash_command(
        name="change_delay", description="STAFF ONLY - adjust Twitter balance monitoring delay"
    )
    async def change_delay(self, interaction=Interaction, *, delay: int = commands.Param(description="Delay between automatic balance posts (seconds). Default is 600.")):
        if self.verify_permissions(interaction):
            self.balance_delay = delay
            await self.hb_send_message(interaction, message=f"Delay has been updated to {delay} seconds. <:MizukiThumbsUp:925566710243803156>")
        else:
            await self.hb_send_message(interaction, message="You're not staff.")
        return

    @commands.slash_command(
        name="toggle_monitoring", description="STAFF ONLY - toggle monitoring for every change"
    )
    async def toggle_monitoring(self, interaction=Interaction):
        if self.verify_permissions(interaction):
            self.monitor_all = not self.monitor_all
            if self.monitor_all:
                await self.hb_send_message(interaction, message="Monitoring has been turned on. <:MizukiThumbsUp:925566710243803156>")
            else:
                await self.hb_send_message(interaction, message="Monitoring has been turned off. <:aifuckedup:566398094980153344>")
        else:
            await self.hb_send_message(interaction, message="You're not staff.")
        return


def setup(bot: commands.Bot):
    bot.add_cog(ARG(bot))
