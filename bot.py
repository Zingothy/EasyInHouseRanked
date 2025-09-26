import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from discord.ui import View
import math
import random
import json
import os
from pokemon import generate_pokemon
import asyncio
import datetime
import time
from itertools import combinations
from itertools import permutations
from trueskill import Rating, quality_1vs1, rate_1vs1
import traceback
from bottokens import tokens # type: ignore
from discord import FFmpegPCMAudio
from PIL import Image, ImageDraw, ImageFont # type: ignore
import io

BOT_TOKEN = tokens.EIHR_token

# Current Rank Emoji
emoji_1 = "<:Bronze:1056655601087828080>"
emoji_2 = "<:Silver:1056655619807006740>"
emoji_3 = "<:Gold:1056655634633867335>"
emoji_4 = "<:Platinum:1056655649922105374>"
emoji_5 = "<:Diamond:1056655665361334372>"
emoji_6 = "<:Master:1056655689155625140>"

# emoji_1 = "🟫"
# emoji_2 = "⬜"
# emoji_3 = "🟨"
# emoji_4 = "🟩"
# emoji_5 = "🟦"
# emoji_6 = "🟥"


def elo_probability(rating1, rating2):
    return 1.0 / (1 + math.pow(10, (rating1 - rating2) / 400.0))

def elo_rating(rankA, rankB, Konstant):
    PA = elo_probability(rankB, rankA) # Probability of winner A winning
    PB = elo_probability(rankA, rankB) # Probability of loser B winning

    rankW = Konstant * 2 * (1 - PA)
    rankL = Konstant * 2 * (-1 * PB)

    return(rankW, rankL) # Return the CHANGE in rank for winners and losers


rankscaling = 1.00173 # µ
async def rankcalc(context, winners, losers, guildstring, undostring): # VERSION 2.14.2 Added match history, peak zsr, elo, ts ~ fixed |*~ formatting #

    botuser = context.guild.me

    bigstring = ""

    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    ### SETUP UNDO
    if not os.path.exists(undostring):
        undodatabase = {}
        with open(undostring, 'w') as file:
            json.dump(undodatabase, file, indent=4)
        # print(f"Undo-Database created for server {undostring}")

    with open(undostring, 'r') as openfile:
        undodatabase = json.load(openfile)

    if "gamedata" not in database:
        database["gamedata"] = {}
    if "rankbase" in database["gamedata"]:
        rankbase = database["gamedata"]["rankbase"]
    else:
        rankbase = 30

    allplayers = winners + losers

    winnerratio = 1
    loserratio = 1

    if len(winners) > len(losers):
        winnerratio = len(losers) / len(winners)
    if len(losers) > len(winners):
        loserratio = len(winners) / len(losers)

    # print(f"Winner Ratio: {winnerratio}\nLoser Ratio: {loserratio}")

    # print(allplayers)

    for x in allplayers:
        # y = database[x]
        # undodatabase[x] = y
        try:
            if x in database:
                undodatabase[x] = database[x]
        except:
            # print("Error, user not added to undo database")
            pass

    with open(undostring, "w") as outfile:
        json.dump(undodatabase, outfile, indent=4)

    for x in winners:
        database[x]["wins"] += 1        # Increase wins in database
        if "seasonwins" in database[x]:
            database[x]["seasonwins"] += 1
        if database[x]["streak"] > 0:   # Increase streak in database
            database[x]["streak"] += 1
        else:
            database[x]["streak"] = 1
    for x in losers:
        database[x]["losses"] += 1      # Increase losses in database
        if "seasonlosses" in database[x]:
            database[x]["seasonlosses"] += 1
        if database[x]["streak"] < 0:   # Decrease streak in database
            database[x]["streak"] -= 1
        else:
            database[x]["streak"] = -1

    if len(winners) == 1 and len(losers) == 1:
        for x in allplayers:
            if "LastOpponent" not in database[x]:
                database[x]["LastOpponent"] = "None"
        for x in winners:
            database[x]["LastOpponent"] = losers[0]
        for x in losers:
            database[x]["LastOpponent"] = winners[0]

    sorttype = "zsr"
    if "gamedata" in database:
        if "mmrtype" in database["gamedata"]:
            if database["gamedata"]["mmrtype"].lower() == "elo":
                sorttype = "elo"
            elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                sorttype = "trueskill"
            else:
                sorttype = "zsr"
        else:
            sorttype = "zsr"
    else:
        sorttype = "zsr"

    if sorttype.lower() == "zsr":
        sortstring = "mmr"
    if sorttype.lower() == "trueskill":
        sortstring = "TrueSkillMu"
    if sorttype.lower() == "elo":
        sortstring = "Elo"

    members = winners + losers
    guild = context.guild

    for x in members:
        if "Elo" not in database[x]:
            database[x]["Elo"] = findstartingelo(guildstring)

    for x in members:
        if "TrueSkillMu" not in database[x]:
            database[x]["TrueSkillMu"] = 25
        if "TrueSkillSigma" not in database[x]:
            database[x]["TrueSkillSigma"] = 8.333

    storage = {}
    for x in members:
        tempmmr = database[x][sortstring]
        storage[x] = [tempmmr, "name", database[x]["uncertainty"]]    # Recording the change in MMR and Uncertainty for later

    #############
    # ZSR2
    #############

    avgwinnermmr = 0
    avglosermmr = 0
    avgwinnerunc = 0
    avgloserunc = 0

    for x in winners:
        avgwinnermmr += database[x]["mmr"]
        avgwinnerunc += database[x]["uncertainty"]
    avgwinnermmr /= len(winners)
    avgwinnerunc /= len(winners)

    for x in losers:
        avglosermmr += database[x]["mmr"]
        avgloserunc += database[x]["uncertainty"]
    avglosermmr /= len(losers)
    avgloserunc /= len(losers)

    flatdifference = avglosermmr - avgwinnermmr  # Gets the difference for our first formula

    serveraveragemmr = 0
    totalmmr = 0
    totalusers = 0

    sorteddb = dict(
        sorted(
            ((k, v) for k, v in database.items() if "mmr" in v),
            key=lambda item: item[1]["mmr"],
            reverse=True))

    for x in sorteddb:
        if database[x]["uncertainty"] < 500:
            totalmmr += database[x]["mmr"]
            totalusers += 1

    if totalusers > 0:
        serveraveragemmr = totalmmr / totalusers
    if totalusers == 0:
        serveraveragemmr = 0

    # serveraveragemmr = (totalmmr + 100) / (totalusers + 1)

    winneradjustedmmr = max((((avgwinnermmr * (1000 - avgwinnerunc) / 1000) + (serveraveragemmr * avgwinnerunc / 1000)) / 2), avgwinnermmr)
    loseradjustedmmr = max((((avglosermmr * (1000 - avgloserunc) / 1000) + (serveraveragemmr * avgloserunc / 1000)) / 2), avglosermmr)

    for x in winners:
        mydifference = rankbase * 2 * (1 - (1 / (1 + (rankscaling ** (loseradjustedmmr - avgwinnermmr)))))
        # print(f"Winner diff no adjust: {mydifference}")
        
        mydifference *= winnerratio
        mydifference = math.ceil(mydifference)

        xuser = await guild.fetch_member(int(x))
        storage[x][1] = xuser.display_name

        database[x]["mmr"] += mydifference

    for x in losers:
        mydifference = rankbase * 2 * (1 - (1 / (1 + (rankscaling ** (avglosermmr - winneradjustedmmr)))))
        # print(f"Loser diff before adjust: {mydifference}")
        mydifference = mydifference * (clamp(database[x]["mmr"], 0, 100)) / 100 # Hardcap-Softcap 0-100
        # print(f"Loser diff after adjust: {mydifference}")
        # try:
        #     print(f"loser100 adjust: {(clamp(database[x]["mmr"], 0, 100)) / 100}")
        # except:
        #     pass
        mydifference *= loserratio
        mydifference = math.ceil(mydifference)

        xuser = await guild.fetch_member(int(x))
        storage[x][1] = xuser.display_name

        database[x]["mmr"] -= mydifference
        if database[x]["mmr"] < 0:
            database[x]["mmr"] = 0

    #############
    # Uncertainty
    #############

    if avglosermmr >= avgwinnermmr + 100:
        for x in allplayers:
            database[x]["uncertainty"] += 50

    if avgwinnermmr >= avglosermmr + 100:
        for x in allplayers:
            database[x]["uncertainty"] -= 50

    if abs(avgwinnermmr - avglosermmr) < 100:
        for x in allplayers:
            # database[x]["uncertainty"] -= 1
            database[x]["uncertainty"] -= 50


    for x in allplayers:
        database[x]["uncertainty"] = math.ceil(database[x]["uncertainty"])
        if database[x]["uncertainty"] < 0:
            database[x]["uncertainty"] = 0
        if database[x]["uncertainty"] > 1000:
            database[x]["uncertainty"] = 1000

    #############
    # ELO
    #############

    avgwinnerelo = 0
    avgloserelo = 0

    for x in winners:
        avgwinnerelo += database[x]["Elo"]
    avgwinnerelo /= len(winners)

    for x in losers:
        avgloserelo += database[x]["Elo"]
    avgloserelo /= len(winners)

    winnergain, loserloss = elo_rating(avgwinnerelo, avgloserelo, rankbase)
    # print(f"Elo: +{winnergain} -{loserloss}")

    for x in winners:
        database[x]["Elo"] += winnergain * winnerratio

    for x in losers:
        database[x]["Elo"] += loserloss * loserratio

    for x in allplayers:
        database[x]["Elo"] = round(database[x]["Elo"])

    #############
    # TrueSkill
    #############

    avgwinnermu = 0
    avglosermu = 0
    avgwinnersigma = 0
    avglosersigma = 0

    for x in winners:
        avgwinnermu += database[x]["TrueSkillMu"]
    avgwinnermu /= len(winners)
    for x in losers:
        avglosermu += database[x]["TrueSkillMu"]
    avglosermu /= len(winners)

    for x in winners:
        avgwinnersigma += database[x]["TrueSkillSigma"]
    avgwinnersigma /= len(winners)
    for x in losers:
        avglosersigma += database[x]["TrueSkillSigma"]
    avglosersigma /= len(winners)

    newwinner = Rating(mu=avgwinnermu, sigma=avgwinnersigma)
    newloser = Rating(mu=avglosermu, sigma=avglosersigma)

    finalwinner, finalloser = rate_1vs1(newwinner, newloser)

    winnerchange = finalwinner.mu - newwinner.mu
    loserchange = finalloser.mu - newloser.mu

    for x in winners:
        database[x]["TrueSkillMu"] += winnerchange * winnerratio
    for x in losers:
        database[x]["TrueSkillMu"] += loserchange * loserratio

    winnerchange = finalwinner.sigma - newwinner.sigma
    loserchange = finalloser.sigma - newloser.sigma

    for x in winners:
        database[x]["TrueSkillSigma"] += winnerchange
        database[x]["TrueSkillSigma"] = max(database[x]["TrueSkillSigma"], 1)
    for x in losers:
        database[x]["TrueSkillSigma"] += loserchange
        database[x]["TrueSkillSigma"] = max(database[x]["TrueSkillSigma"], 1)

    #############
    # Head 2 Head
    #############
    for x in allplayers:
        if "Head2Head" not in database[x]:
            database[x]["Head2Head"] = {}
        for y in allplayers:
            if "Head2Head" not in database[y]:
                database[y]["Head2Head"] = {}
            if x != y:
                if y not in database[x]["Head2Head"]:
                    database[x]["Head2Head"][y] = [0, 0]
                if x not in database[y]["Head2Head"]:
                    database[y]["Head2Head"][x] = [0, 0]

    for x in winners:
        for y in losers:
            database[x]["Head2Head"][y][0] += 1
            database[y]["Head2Head"][x][1] += 1

    #############
    # DATABASE and OUTPUT
    #############

    for x in allplayers:
        trueskilldelta = database[x]["TrueSkillMu"] - 3 * database[x]["TrueSkillSigma"]

        if "zsrhistory" not in database[x]:
            database[x]["zsrhistory"] = []
        if "elohistory" not in database[x]:
            database[x]["elohistory"] = []
        if "tshistory" not in database[x]:
            database[x]["tshistory"] = []

        database[x]["zsrhistory"].append(database[x]["mmr"])
        if len(database[x]["zsrhistory"]) > 200:
            database[x]["zsrhistory"] = database[x]["zsrhistory"][1:]

        database[x]["elohistory"].append(database[x]["Elo"])
        if len(database[x]["elohistory"]) > 200:
            database[x]["elohistory"] = database[x]["elohistory"][1:]

        database[x]["tshistory"].append(trueskilldelta)
        if len(database[x]["tshistory"]) > 200:
            database[x]["tshistory"] = database[x]["tshistory"][1:]

        if "peakzsr" not in database[x]:
            database[x]["peakzsr"] = database[x]["mmr"]
        if "peakelo" not in database[x]:
            database[x]["peakelo"] = database[x]["Elo"]
        if "peakts" not in database[x]:
            database[x]["peakts"] = trueskilldelta

        if database[x]["mmr"] > database[x]["peakzsr"]:
            database[x]["peakzsr"] = database[x]["mmr"]
        if database[x]["Elo"] > database[x]["peakelo"]:
            database[x]["peakelo"] = database[x]["Elo"]
        if trueskilldelta > database[x]["peakts"]:
            database[x]["peakts"] = trueskilldelta

    if "gamedata" not in database:
        database["gamedata"] = {}
    if "mastertier" in database["gamedata"]:
        tier2 = database["gamedata"]["silvertier"]
        tier3 = database["gamedata"]["goldtier"]
        tier4 = database["gamedata"]["platinumtier"]
        tier5 = database["gamedata"]["diamondtier"]
        tier6 = database["gamedata"]["mastertier"]
    else:
        tier2 = 200
        tier3 = 400
        tier4 = 600
        tier5 = 800
        tier6 = 1000

    debugstring = ""
    bigstring = ("Winners:")
    for x in winners:
        name = storage[x][1]
        name = name.replace("_", "\x5c_")
        name = name.replace("||", "\\||")
        name = name.replace("*", "\\*")
        name = name.replace("~~", "\\~~")

        change = storage[x][0] - database[x][sortstring]

        mmr = database[x][sortstring]

        oldunc = storage[x][2]
        newunc = database[x]["uncertainty"]

        emoji_1, emoji_2, emoji_3, emoji_4, emoji_5, emoji_6 = loademoji(guildstring)

        emoji = emoji_1
        if mmr >= tier2:
            emoji = emoji_2
        if mmr >= tier3:
            emoji = emoji_3
        if mmr >= tier4:
            emoji = emoji_4
        if mmr >= tier5:
            emoji = emoji_5
        if mmr >= tier6:
            emoji = emoji_6

        if sortstring == "TrueSkillMu":
            tempmmr = float(storage[x][0])
            tempmmr = round(tempmmr, 2)
            storage[x][0] = tempmmr
            mmr = round(mmr, 2)

        debugstring += (f"\n{name}: {storage[x][0]} ~> **{mmr}** *({oldunc}u ~> {newunc}u)*")
        bigstring += (f"\n{name}: {storage[x][0]} ~> {emoji}**{mmr}**{emoji}")

    bigstring += (f"\nLosers:")

    for x in losers:
        name = storage[x][1]
        name = name.replace("_", "\x5c_")
        name = name.replace("||", "\\||")
        name = name.replace("*", "\\*")
        name = name.replace("~~", "\\~~")

        change = storage[x][0] - database[x][sortstring]

        mmr = database[x][sortstring]

        oldunc = storage[x][2]
        newunc = database[x]["uncertainty"]

        emoji = emoji_1
        if mmr >= tier2:
            emoji = emoji_2
        if mmr >= tier3:
            emoji = emoji_3
        if mmr >= tier4:
            emoji = emoji_4
        if mmr >= tier5:
            emoji = emoji_5
        if mmr >= tier6:
            emoji = emoji_6

        if sortstring == "TrueSkillMu":
            tempmmr = float(storage[x][0])
            tempmmr = round(tempmmr, 2)
            storage[x][0] = tempmmr
            mmr = round(mmr, 2)

        debugstring += (f"\n{name}: {storage[x][0]} ~> **{mmr}** *({oldunc}u ~> {newunc}u)*")
        bigstring += (f"\n{name}: {storage[x][0]} ~> {emoji}**{mmr}**{emoji}")
    bigstring += ("\n")

    # bigstring = "<a:arrowright:1319062838332883045> **Match submitted!**\n" + bigstring

    embed = discord.Embed(
            description = bigstring,
            title = "**Match submitted!**"
            )
    
    print(debugstring)

    #############
    # SERVER ROLES
    #############

    if "rankroles" in database:
        guild = context.guild
        botuser = context.guild.me
        permissions1 = botuser.guild_permissions.manage_roles
        mastername = database["rankroles"]["master"]
        masterrole = discord.utils.get(guild.roles, name=mastername)
        bothasrolepermissions = False
        for x in botuser.roles:
            try:
                if x > masterrole:
                    if permissions1:
                        bothasrolepermissions = True
            except:
                pass
                    
        if bothasrolepermissions:
            try:
                guild = client.get_guild(int(guildstring[:-5]))
                bronzename = database["rankroles"]["bronze"]
                bronzerole = discord.utils.get(guild.roles, name=bronzename)
                silvername = database["rankroles"]["silver"]
                silverrole = discord.utils.get(guild.roles, name=silvername)
                goldname = database["rankroles"]["gold"]
                goldrole = discord.utils.get(guild.roles, name=goldname)
                platname = database["rankroles"]["platinum"]
                platrole = discord.utils.get(guild.roles, name=platname)
                diamondname = database["rankroles"]["diamond"]
                diamondrole = discord.utils.get(guild.roles, name=diamondname)
                mastername = database["rankroles"]["master"]
                masterrole = discord.utils.get(guild.roles, name=mastername)

                for x in allplayers:

                    mmr = database[x]["mmr"]
                    user = await guild.fetch_member(int(x))

                    newtier = 1
                    if mmr >= tier2:
                        newtier = 2
                    if mmr >= tier3:
                        newtier = 3
                    if mmr >= tier4:
                        newtier = 4
                    if mmr >= tier5:
                        newtier = 5
                    if mmr >= tier6:
                        newtier = 6
                    
                    
                    if newtier != 1:
                        if bronzerole in user.roles:
                            await user.remove_roles(bronzerole)
                    if newtier != 2:
                        if silverrole in user.roles:
                            await user.remove_roles(silverrole)
                    if newtier != 3:
                        if goldrole in user.roles:
                            await user.remove_roles(goldrole)
                    if newtier != 4:
                        if platrole in user.roles:
                            await user.remove_roles(platrole)
                    if newtier != 5:
                        if diamondrole in user.roles:
                            await user.remove_roles(diamondrole)
                    if newtier != 6:
                        if masterrole in user.roles:
                            await user.remove_roles(masterrole)

                    if newtier == 1:
                        if bronzerole not in user.roles:
                            await user.add_roles(bronzerole)
                    if newtier == 2:
                        if silverrole not in user.roles:
                            await user.add_roles(silverrole)
                    if newtier == 3:
                        if goldrole not in user.roles:
                            await user.add_roles(goldrole)
                    if newtier == 4:
                        if platrole not in user.roles:
                            await user.add_roles(platrole)
                    if newtier == 5:
                        if diamondrole not in user.roles:
                            await user.add_roles(diamondrole)
                    if newtier == 6:
                        if masterrole not in user.roles:
                            await user.add_roles(masterrole)                

            except:
                bigstring = "Error with changing ranked roles. Check the bot's roles/permissions\n" + bigstring

    with open(guildstring, "w") as outfile:
        json.dump(database, outfile, indent = 4)

    # print(bigstring)
    # return(bigstring)
    return(embed)


def clamp(num, min_value, max_value):
    return max(min(num, max_value), min_value)


async def generatequeuetext(interaction, guildstring): # 2.1 now checks for none #
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    first = True
    newstring = ""

    queuetextbool = False

    if "queuetext" in database:
        queuetextbool = True
        
        for x in database["queuetext"]:
            if x in ["lista", "listb", "listc", "listd", "liste", "listf", "listg", "listh", "listi", "listj"]:
                if x not in ["None", "", "none", "null", None]:
                    queuetextbool = False


        if queuetextbool == True:
            newstring = "<a:arrowright:1319062838332883045> "
            for x in database["queuetext"]:
                if x in ["lista", "listb", "listc", "listd", "liste", "listf", "listg", "listh", "listi", "listj"]:
                    content = database["queuetext"][x]
                    if isinstance(content, str):
                        list = content.split(",")

                        if first == False:
                            newstring += " - "
                        else:
                            first = False

                        try:
                            newstring += random.choice(list)
                        except:
                            pass

            if "digits" in database["queuetext"]:
                digits = database["queuetext"]["digits"]
                if isinstance(digits, int):
                    number = (10 ** digits) - 1
                    if newstring != "":
                        newstring += " - "
                    newstring += str(random.randint(1, number))      

            newstring += " <a:arrowleft:1319062852929064990>"  

    return newstring


def findstartingelo(guildstring):
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    try:
        if "startingelo" in database["gamedata"]:
            if isinstance(database["gamedata"]["startingelo"], int):
                return database["gamedata"]["startingelo"]
            else:
                return 1000
        else:
            return 1000
    except:
        return 1000


def loademoji(guildstring):
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if "rankemoji" in database:
        bronze = database["rankemoji"]["bronze"]
        silver = database["rankemoji"]["silver"]
        gold = database["rankemoji"]["gold"]
        plat = database["rankemoji"]["plat"]
        diamond = database["rankemoji"]["diamond"]
        master = database["rankemoji"]["master"]
    
    else:
        bronze = "<:Bronze:1056655601087828080>"
        silver = "<:Silver:1056655619807006740>"
        gold = "<:Gold:1056655634633867335>"
        plat = "<:Platinum:1056655649922105374>"
        diamond = "<:Diamond:1056655665361334372>"
        master = "<:Master:1056655689155625140>"

    return bronze, silver, gold, plat, diamond, master


class CommandTree(app_commands.CommandTree):
    async def on_error(self, interaction: discord.Interaction, error: app_commands.CommandInvokeError) -> None:
        print("~~~~~\nZing custom error:")
        print(error)
        if interaction.guild:
            print(f"Guild: {interaction.guild.name} ~ {interaction.guild.id}")
        print("~~~~~")

        # if "FileNotFoundError" in str(error):
            # await interaction.response.send_message("Database not found. Create your server's database with **/setup**\ntry **/help** and **/faq** if youre still confused", ephemeral=True)

        user = interaction.user
        dmchannel = await user.create_dm()
        await dmchannel.send(content="You ran into an error with a command! Try **/help** and **/faq**\nIf youre still stuck, join our support server:\nhttps://discord.gg/Hq4ee6qkU8")


class Client(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="}",
            intents=intents,
            tree_cls=CommandTree,
            activity=discord.CustomActivity(name="/help /faq")
        )

    async def on_ready(self):
        print(f"logged on as {self.user}")

        try:
            guild = discord.Object(id=1263283045616582757)
            synced = await self.tree.sync(guild=guild) # private commands?
            synced = await client.tree.sync() # public commands?

            # print(f"synched {len(synced)} command(s)")
        except Exception as e:
            print(e)
            # pass


guildid = discord.Object(id=1263283045616582757)
intents = discord.Intents.default()
intents.members = True
client = Client()


@client.tree.command(name="sync", description="Sync EIHR commands", guild=guildid) # Slash command 0.1
async def sync(interaction: discord.Interaction):
    if interaction.user.id == 215277233638604800:
        try:
            synced = await client.tree.sync(guild=guildid) # private commands?
            synced = await client.tree.sync() # public commands?
            await interaction.response.send_message(f"Synced command(s)", ephemeral=True)
            print("Synced command(s)")
        except:
            await interaction.response.send_message(f"Error syncing commands")
            print("Error syncing commands")


@client.tree.command(name="help", description="Show the full list of commands and their permission levels.") # 1.2 more arrows by /setup
async def help(interaction: discord.Interaction):
    await interaction.response.send_message("**Command list:**\n<a:arrowright:1319062838332883045>**Public Commands:**\n"
    "**/help:** Shows a list of commands\n"
    "**/setup:** Creates your server's database <a:arrowleft:1319062852929064990><a:arrowleft:1319062852929064990><a:arrowleft:1319062852929064990><a:arrowleft:1319062852929064990>\n"
    "**/faq:** Frequently asked questions and answers\n"
    "**/win:** Submit a game with winners and losers\n"
    "**/leaderboard:** Shows your server's leaderboard\n"
    "**/oldleaderboard:** Shows your server's leaderboard in plaintext\n"
    "**/show:** Shows a user's detailed stats\n"
    "**/headtohead:** Shows someone's head-to-head records\n"
    "<a:arrowright:1319062838332883045>**Lv 1 Commands:** Requires Lv 1 access\n"
    "**/showconfig:** Show's your server's config file\n"
    "**/undorank:** Undoes a user's last ranked game. (must be done individually for each user)\n"
    "**/forcewin:** Automatically submit and approve a ranked game\n"
    "**/queue:** Start a matchmaking queue\n"
    "**/rankban:** Ban a user from ranked\n"
    "**/rankunban:** Unban a user from ranked\n", ephemeral=True)
    await interaction.followup.send("<a:arrowright:1319062838332883045>**Lv 2 Commands:** Requires Lv 2 access\n"
    "**/configgame:** Set the name of the game. (does nothing by itself, mostly unused currently)\n"
    "**/configseason:** Set the name of the current season\n"
    "**/adjustuser:** Set the MMR(ZSR), Elo, wins, etc of a user\n"
    "**/backup:** Creates a backup of your server's database and posts it for download. (This can be sent to Zing if you need your backup restored)\n"
    "**/refreshroles:** If your user's ranked roles are not updated, this command will update them\n"
    "**/configmmrtype:** Sets your server's default mmr type ~ Premium command!\n"
    "**/configemoji:** Set your server's ranked emoji ~ Premium command!\n"
    "**/configqueuetext:** Configure random text to go with your queue\n"
    "<a:arrowright:1319062838332883045>**LV 3 Commands:** Requires Lv 3 access\n"
    "**/configrole:** Set a server role's permission access level <a:arrowleft:1319062852929064990><a:arrowleft:1319062852929064990><a:arrowleft:1319062852929064990><a:arrowleft:1319062852929064990>\n"
    "**/configstartelo:** Sets your server's starting Elo (not ZSR)\n"
    "**/configranktiers:** Set what ZSR is required to hit each tier\n"
    "**/configrankbase:** Set what base value determines MMR gains and losses (ZSR and Elo)\n"
    "**/configrankroles:** Set what server roles are given for each rank\n"
    "**/newseason:** Start a new ranked season, with optional soft or hard MMR and Elo resets\n"
    "https://discord.gg/Hq4ee6qkU8", ephemeral=True)


@client.tree.command(name="setup", description="Create your server's database") # Slash command 0.1
async def setup(interaction: discord.Interaction):
    guildstring = str(interaction.guild.id) + ".json"
    if not os.path.exists(guildstring):
        database = {}
        with open(guildstring, 'w') as file:
            json.dump(database, file, indent=4)
        await interaction.response.send_message(f"Database created for server {str(interaction.guild.id)}")
        print(f"Database created for server {str(interaction.guild.id)}")

    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    haslist = False
    count = 0
    for key, value in database.items():
        if isinstance(value, list):
            haslist = True
            count += 1
            mmr = max(database[key][1], database[key][1])
            wins = database[key][2] + database[key][7]
            loss = database[key][3] + database[key][8]
            streak = max(database[key][5], database[key][10])
            uncertainty = 1000
            database[key] = {"mmr": mmr, "wins": wins, "losses": loss, "streak": streak, "uncertainty": uncertainty}

    if haslist == True:
        await interaction.response.send_message(f"{count} database entries updated")

    with open(guildstring, "w") as outfile:
        json.dump(database, outfile, indent=4)


@client.tree.command(name="faq", description="Show some frequently asked questions and answers about Easy In-House Ranked")
async def faq(interaction: discord.Interaction):
    await interaction.response.send_message(f"""**How do I get the bot to join my server?**\nGo to <https://discord.gg/Hq4ee6qkU8> and view the 'about' channel.\n
    **I just invited the bot and nothing is working**\nDo /setup to create your server's database. Then do /configrole to give permissions to discord roles.\n
    **Still nothing is working**\nMake sure that the bot has role permissions to send messages in the channel. Then right click the bot and go to apps, then manage server integration, and make sure the bot's commands are enabled.\n
    **Buttons are not working**\nSometimes the bot loses connection or crashes. Redo the text command.\n
    **Commands were working but are not anymore**\nSometimes the bot loses connection or crashes. Wait 20 seconds or so. If things still aren't working, ping Zing in the support server""", ephemeral=True)
    await interaction.followup.send(
    """**Why does the bot ask for permission to manage roles?**\nThis is for the configurable 'ranked roles' feature. This is fully optional and you can refuse to give the bot permissions when inviting it to your server.\n
    **How does the queue work?**\nStart the queue by typing /queue, then press 'Join Queue' to queue up for a game. The queue will then try to match people together for a game. This may take a few minutes as it tries to find the best game. This is still a WIP and may not work properly.\n
    **How does X ranking system work?**\nZSR stands for 'Zing's Skill Ranking' (This is the default system) <https://docs.google.com/document/d/1mltKn8DoJwocRxjVKYutTM5FoSKkntKzpB5_0EwkVKI/edit?usp=sharing> (current ver. 2.2)\nElo: <https://en.wikipedia.org/wiki/Elo_rating_system>\nTrueskill: <https://en.wikipedia.org/wiki/TrueSkill> *(Trueskill treats all games as 1v1, using an average of the player's values)*\n
    **Where is the support server?**\n<https://discord.gg/Hq4ee6qkU8>\n
    **Where is the Terms of Service and Privacy Policy?**\n<https://docs.google.com/document/d/16NLoryJxJiBcaa9aFbDHA9fFJLtvdYujAwNseUcEyDs/edit?usp=sharing> <https://docs.google.com/document/d/1bkG66OTPzL5sHJY4TxUscfPPz3irqSzU8A3-2k02WDM/edit?usp=sharing>""", ephemeral=True)


@client.tree.command(name="debug", description="Send some info to Zing") # 1.3 sends to bot logs channel #
async def debug(interaction: discord.Interaction):
    user = interaction.user
    userid = user.id
    y = ""

    debugstring = "\n--------------------\nDebug\n"

    debugstring += f"Username: {user} ~ {userid}\n"

    if not interaction.guild:
        debugstring += "not interaction.guild\n"

    if interaction.guild:
        debugstring += "interaction.guild\n"
        guildid = str(interaction.guild.id)
        guildname = str(interaction.guild.name)
        debugstring += f"Guild name: {guildname}\n"
        debugstring += f"Guild ID: {guildid}\n"

        guildstring = guildid + ".json"

        try:
            with open(guildstring, 'r') as openfile:
                database = json.load(openfile)
            debugstring += f"Database found: {guildstring}\n"
        except:
            debugstring += f"No database found: {guildid}\n" 

        if "serverroles" in database:
            debugstring += "Database/Server Roles:\n"
            for x in database["serverroles"]:
                if database["serverroles"][x] == 0:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        y = "(I have this role)"
                    else:
                        y = ""
                    debugstring += f"{x}: Level 0 perms {y}\n"

                if database["serverroles"][x] == 1:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        y = "(I have this role)"
                    else:
                        y = ""
                    debugstring += f"{x}: Level 1 perms {y}\n"

                if database["serverroles"][x] == 2:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        if myrole in user.roles:
                            y = "(I have this role)"
                        else:
                            y = ""
                        debugstring += f"{x}: Level 2 perms {y}\n"

                if database["serverroles"][x] == 3:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        if myrole in user.roles:
                            y = "(I have this role)"
                        else:
                            y = ""
                        debugstring += f"{x}: Level 3 perms {y}\n"

        else:
            debugstring += "serverroles not in database\n"

        # except:
        #     print(f"No database found for {guildname} ~ {guildid}")

        for x in interaction.guild.roles:
            if x.permissions.manage_guild == True or x.permissions.administrator == True:
                if x in user.roles:
                    y = "(I have this role)"
                else:
                    y = ""
                print(f"{x}: Admin/Manage Server - Level 3 perms {y}")

        if "gamedata" in database:
            debugstring += "gamedata in database\n"
            if "gamename" in database["gamedata"]:
                debugstring += f"Game name: {database['gamedata']['gamename']}\n"

            if "season" in database["gamedata"]:
                debugstring += f"Season: {database['gamedata']['season']}\n"

            if "rankbase" in database["gamedata"]:
                debugstring += f"Rank base: {database['gamedata']['rankbase']}\n"

            if "mastertier" in database["gamedata"]:
                debugstring += "Ranked tiers: 0, " + str(database["gamedata"]["silvertier"]) + ", " + str(database["gamedata"]["goldtier"]) + ", " + str(database["gamedata"]["platinumtier"]) + ", " + str(database["gamedata"]["diamondtier"]) + ", " + str(database["gamedata"]["mastertier"]) + "\n"

            if "startingelo" in database["gamedata"]:
                debugstring += f"Starting Elo: {database['gamedata']['startingelo']}\n"

            if "mmrtype" in database["gamedata"]:
                debugstring += f"MMR type: {database['gamedata']['mmrtype']}\n"

        if "rankroles" in database["gamedata"]:
            debugstring += "Rank roles:\n"
            debugstring += f"Bronze: {database['rankroles']['bronze']}\n"
            debugstring += f"Silver: {database['rankroles']['silver']}\n"
            debugstring += f"Gold: {database['rankroles']['gold']}\n"
            debugstring += f"Platinum: {database['rankroles']['platinum']}\n"
            debugstring += f"Diamond: {database['rankroles']['diamond']}\n"
            debugstring += f"Master: {database['rankroles']['master']}\n"


        async for x in client.entitlements(user=interaction.user):
            if x.sku_id == 1361516425172357320:
                debugstring += "Has entitlement: configmmrtype 1361516425172357320\n"
            if x.sku_id == 1380004058797965392:
                debugstring += "Has entitlement: configemoji 1380004058797965392\n"

        if "rankemoji" in database:
            debugstring += f"Rank Emoji:\nBronze: {database["rankemoji"]["bronze"]}\nSilver: {database["rankemoji"]["silver"]}\nGold: {database["rankemoji"]["gold"]}\nPlatinum: {database["rankemoji"]["plat"]}\nDiamond: {database["rankemoji"]["diamond"]}\nMaster: {database["rankemoji"]["master"]}\n"

        guild = interaction.guild
        botuser = interaction.guild.me
        permissions1 = botuser.guild_permissions.manage_roles
        
        bothasrolepermissions = False
        if "rankroles" in database["gamedata"]:
            bronzename = database["rankroles"]["bronze"]
            bronzerole = discord.utils.get(guild.roles, name=bronzename)
            silvername = database["rankroles"]["silver"]
            silverrole = discord.utils.get(guild.roles, name=silvername)
            goldname = database["rankroles"]["gold"]
            goldrole = discord.utils.get(guild.roles, name=goldname)
            platname = database["rankroles"]["platinum"]
            platrole = discord.utils.get(guild.roles, name=platname)
            diamondname = database["rankroles"]["diamond"]
            diamondrole = discord.utils.get(guild.roles, name=diamondname)
            mastername = database["rankroles"]["master"]
            masterrole = discord.utils.get(guild.roles, name=mastername)

            if permissions1:
                for x in botuser.roles:
                    if x > masterrole:
                        if x > diamondrole:
                            if x > platrole:
                                if x > goldrole:
                                    if x > silverrole:
                                        if x > bronzerole:
                                            bothasrolepermissions = True

        debugstring += f"Bot manage roles permission: {bothasrolepermissions}\n"

        if "queuetext" in database:
            debugstring += "queuetext in database\n"

            for x in database["queuetext"]:
                if x in ["lista", "listb", "listc", "listd", "liste", "listf", "listg", "listh", "listi", "listj"]:
                    try:
                        debugstring += database["queuetext"][x] + "\n"
                    except:
                        pass

            if "digits" in database["queuetext"]:
                try:
                    debugstring += "Digits: " + database["queuetext"]["digits"] + "\n"
                except:
                    pass

    # name1 = str(bot.get_user(int(userid)))
    # name2 = str(bot.get_user(str(userid)))
    # name3 = str(await bot.fetch_user(int(userid)))
    # name4 = str(await bot.fetch_user(str(userid)))
    # print(f"\nUser Name: {name1} {name2} {name3} {name4}")

    debugstring += ("Debug\n--------------------\n")

    channel = await client.fetch_channel(1353033947663175760)
    await channel.send(debugstring)
    print(debugstring)

    await interaction.response.send_message("*Debug sent to Zing*\n*If you need help, join our support server* https://discord.gg/Hq4ee6qkU8", ephemeral=True)


@client.tree.command(name="showconfig", description="Show your server's config file") # 1.2 Added queuetext
async def showconfig(interaction: discord.Interaction):
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        user = interaction.user
        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 1:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True
        
        if valid == True:
            if "serverroles" not in database:
                database["serverroles"] = {}

            bigstring = ("**Server roles and permission levels:**\n")

            for x in database["serverroles"]:
                if database["serverroles"][x] > 0:
                    bigstring = bigstring + x + ": " + str(database["serverroles"][x]) + "\n"

            if "gamedata" not in database:
                database["gamedata"] = {}

            bigstring = bigstring + "**Server game data:**\n"

            if "gamename" in database["gamedata"]:
                bigstring = bigstring + "Game name (wip): " + database["gamedata"]["gamename"] + "\n"

            if "season" in database["gamedata"]:
                bigstring = bigstring + "Season: " + str(database["gamedata"]["season"]) + "\n"

            if "rankbase" in database["gamedata"]:
                bigstring = bigstring + "Rank Base: " + str(database["gamedata"]["rankbase"]) + "\n"

            if "mastertier" in database["gamedata"]:
                bigstring = bigstring + "Ranked tiers: 0, " + str(database["gamedata"]["silvertier"]) + ", " + str(database["gamedata"]["goldtier"]) + ", " + str(database["gamedata"]["platinumtier"]) + ", " + str(database["gamedata"]["diamondtier"]) + ", " + str(database["gamedata"]["mastertier"]) + "\n"

            if "startingelo" in database["gamedata"]:
                bigstring = bigstring + "Starting Elo: " + str(database["gamedata"]["startingelo"]) + "\n"

            if "rankroles" in database:
                bigstring = bigstring + "**Rank Roles:**\n"
                tempstring = (f"Bronze: {database["rankroles"]["bronze"]}\nSilver: {database["rankroles"]["silver"]}\nGold: {database["rankroles"]["gold"]}\nPlatinum: {database["rankroles"]["platinum"]}\nDiamond: {database["rankroles"]["diamond"]}\nMaster: {database["rankroles"]["master"]}")
                bigstring = bigstring + tempstring

            if "rankemoji" in database:
                bigstring = bigstring + "**Rank Emoji:**\n"
                tempstring = (f"Bronze: {database["rankemoji"]["bronze"]}\nSilver: {database["rankemoji"]["silver"]}\nGold: {database["rankemoji"]["gold"]}\nPlatinum: {database["rankemoji"]["plat"]}\nDiamond: {database["rankemoji"]["diamond"]}\nMaster: {database["rankemoji"]["master"]}\n")
                bigstring = bigstring + tempstring

            if "mmrtype" in database["gamedata"]:
                bigstring = bigstring + "MMR type: " + str(database["gamedata"]["mmrtype"]) + "\n"

            if "queuetext" in database:
                bigstring = bigstring + "**Queue Text:**"
                for x in database["queuetext"]:
                    if x in ["lista", "listb", "listc", "listd", "liste", "listf", "listg", "listh", "listi", "listj"]:
                        bigstring = bigstring + "\n" + database["queuetext"][x]
                if "digits" in database["queuetext"]:
                    bigstring = bigstring + "\nDigits: " + str(database["queuetext"]["digits"]) + "\n"
            
            await interaction.response.send_message(bigstring)

            print(f"\nShowconfig in {guildname}")
            try:
                print(database["serverroles"])
            except:
                pass
            try:
                print(database["gamedata"])
            except:
                pass
            try:
                print(database["rankemoji"])
            except:
                pass
            try:
                print(database["queuetext"])
            except:
                pass
            print()


@client.tree.command(name="configemoji", description="PREMIUM FEATURE ~ WIP ~ Set custom emoji for each ranked tier") # 1.0 implemented check for purchase #
@app_commands.describe(bronze = "Which emoji will be given for Bronze?")
@app_commands.describe(silver = "Which emoji will be given for Silver?")
@app_commands.describe(gold = "Which emoji will be given for Gold?")
@app_commands.describe(plat = "Which emoji will be given for Platinum?")
@app_commands.describe(diamond = "Which emoji will be given for Diamond?")
@app_commands.describe(master = "Which emoji will be given for Master?")
async def configemoji(interaction: discord.Interaction, bronze: str, silver: str, gold: str, plat: str, diamond: str, master: str):
    user = interaction.user
    valid = False
    paid = False

    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 2:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if valid == True:
        async for x in client.entitlements(user=interaction.user):
            if x.sku_id == 1380004058797965392: # TODO?
                paid = True

    if str(user.id) == "215277233638604800":
        paid = True
    
    if valid == False or paid == False:
        await interaction.response.send_message("You do not have permission to use this command. (This is a premium feature)", ephemeral=True)

    if valid == True and paid == True:
        if "rankemoji" not in database:
            database["rankemoji"] = {}

        database["rankemoji"]["bronze"] = bronze
        database["rankemoji"]["silver"] = silver
        database["rankemoji"]["gold"] = gold
        database["rankemoji"]["plat"] = plat
        database["rankemoji"]["diamond"] = diamond
        database["rankemoji"]["master"] = master

        await interaction.response.send_message(f"Ranked emoji set: {bronze} {silver} {gold} {plat} {diamond} {master}")

        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)


@client.tree.command(name="configrole", description="Configure your server's role permissions") # Slash command 0.1
@app_commands.describe(inputrole = "Which role?")
@app_commands.describe(chooselevel = "Permission Level: 0, 1, 2, 3")
async def configrole(interaction: discord.Interaction, inputrole: discord.guild.Role, chooselevel: str):
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" not in database:
            database["serverroles"] = {}

        if chooselevel in ["0", "1", "2", "3"]:
            chooselevel = int(chooselevel)
            user = interaction.user
            rolename = inputrole.name
            
            if inputrole is not None:
                if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                    valid = True

                for x in database["serverroles"]:
                    if database["serverroles"][x] >= 3:
                        myrole = discord.utils.get(interaction.guild.roles, name=x)
                        if myrole in user.roles:
                            valid = True

                if valid == True:
                    rolename = str(inputrole)
                    database["serverroles"][rolename] = chooselevel
                    print(guildstring)
                    print(database["serverroles"])

                    await interaction.response.send_message(f"{rolename} set to level {chooselevel}")

                    with open(guildstring, "w") as outfile:
                        json.dump(database, outfile, indent=4)

            else:
                await interaction.response.send_message("Error: Role not found")

        # if rolename == "" and chooselevel == "":
        #     await interaction.response.send_message(f"?config <Role Name> <Permission Level (0, 1, 2, 3)>\nRequires 'administrator' or 'Manage Server' permissions or lv 3 permissions")


@client.tree.command(name="configgame", description="Configure your server's game name") # Slash command 0.1
@app_commands.describe(inputname = "What is the name of your game?")
async def configgame(interaction: discord.Interaction, inputname: str):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" not in database:
            database["serverroles"] = {}

        if inputname is not None:
            if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                valid = True

            for x in database["serverroles"]:
                if database["serverroles"][x] >= 2:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

            if valid == True:
                if "gamedata" not in database:
                    database["gamedata"] = {}

                database["gamedata"]["gamename"] = inputname

                await interaction.response.send_message(f"Server game name changed to {inputname}")

                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent=4)


@client.tree.command(name="configstartelo", description="Configure your server's starting elo") # Slash command 0.1
@app_commands.describe(inputelo = "What elo do you want new players to start at? (default 1000)")
async def configstartelo(interaction: discord.Interaction, inputelo: int):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" not in database:
            database["serverroles"] = {}

        if inputelo is not None:
            if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                valid = True

            for x in database["serverroles"]:
                if database["serverroles"][x] >= 3:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

            if valid == True:
                if "gamedata" not in database:
                    database["gamedata"] = {}

                database["gamedata"]["startingelo"] = inputelo

                await interaction.response.send_message(f"Starting Elo set to {inputelo}")

                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent=4)


@client.tree.command(name="configranktiers", description="Configure which values are required to hit each rank") # Slash command 0.1
@app_commands.describe(silver = "How many ZSR points required to hit Silver?")
@app_commands.describe(gold = "How many ZSR points required to hit Gold?")
@app_commands.describe(plat = "How many ZSR points required to hit Platinum?")
@app_commands.describe(diamond = "How many ZSR points required to hit Diamond?")
@app_commands.describe(master = "How many ZSR points required to hit Master?")
async def configranktiers(interaction: discord.Interaction, silver: int, gold: int, plat: int, diamond: int, master: int):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" not in database:
            database["serverroles"] = {}

        if None not in (silver, gold, plat, diamond, master):
            if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                valid = True

            for x in database["serverroles"]:
                if database["serverroles"][x] >= 3:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

            if valid == True:
                if "gamedata" not in database:
                    database["gamedata"] = {}

                database["gamedata"]["silvertier"] = silver
                database["gamedata"]["goldtier"] = gold
                database["gamedata"]["platinumtier"] = plat
                database["gamedata"]["diamondtier"] = diamond
                database["gamedata"]["mastertier"] = master

                emoji_1, emoji_2, emoji_3, emoji_4, emoji_5, emoji_6 = loademoji(guildstring)

                await interaction.response.send_message(f"Tiers updated:\n{emoji_1}Bronze: 0\n{emoji_2}Silver: {silver}\n{emoji_3}Gold: {gold}\n{emoji_4}Platinum: {plat}\n{emoji_5}Diamond: {diamond}\n{emoji_6}Master: {master}")

                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent=4)


@client.tree.command(name="configrankbase", description="Configure your server's base rank change value (recommended: 10 - 60)") # 1.1 updated description # 
@app_commands.describe(inputbase = "What base value do you want to determine players ZSR and Elo gains/losses? (default 30)")
async def configrankbase(interaction: discord.Interaction, inputbase: int):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" not in database:
            database["serverroles"] = {}

        if inputbase is not None:
            if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                valid = True

            for x in database["serverroles"]:
                if database["serverroles"][x] >= 3:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

            if valid == True:
                if "gamedata" not in database:
                    database["gamedata"] = {}

                database["gamedata"]["rankbase"] = inputbase

                await interaction.response.send_message(f"Changed rank base value to {inputbase}")

                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent=4)                


@client.tree.command(name="configseason", description="Change the name of the current season") # Slash command 0.1
@app_commands.describe(inputseason = "What is the name of the current season?")
async def configseason(interaction: discord.Interaction, inputseason: str):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" not in database:
            database["serverroles"] = {}

        if inputseason is not None:
            if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                valid = True

            for x in database["serverroles"]:
                if database["serverroles"][x] >= 2:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

            if valid == True:
                if "gamedata" not in database:
                    database["gamedata"] = {}
                database["gamedata"]["season"] = inputseason

                await interaction.response.send_message(f"Season set to {inputseason}")

                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent=4)            


@client.tree.command(name="configrankroles", description="Configure which roles will be given for each rank.") # Slash command 0.1
@app_commands.describe(bronze = "Which role will be given for Bronze?")
@app_commands.describe(silver = "Which role will be given for Silver?")
@app_commands.describe(gold = "Which role will be given for Gold?")
@app_commands.describe(plat = "Which role will be given for Platinum?")
@app_commands.describe(diamond = "Which role will be given for Diamond?")
@app_commands.describe(master = "Which role will be given for Master?")
async def configrankroles(interaction: discord.Interaction, bronze: discord.guild.Role, silver: discord.guild.Role, gold: discord.guild.Role, plat: discord.guild.Role, diamond: discord.guild.Role, master: discord.guild.Role):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if None not in (bronze, silver, gold, plat, diamond, master):
            if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
                valid = True

            if "serverroles" in database:
                for x in database["serverroles"]:
                    if database["serverroles"][x] >= 3:
                        myrole = discord.utils.get(interaction.guild.roles, name=x)
                        if myrole in user.roles:
                            valid = True

            if valid == True:
                bronze = bronze.name
                silver = silver.name
                gold = gold.name
                plat = plat.name
                diamond = diamond.name
                master = master.name

                database["rankroles"] = {"bronze": bronze, "silver": silver, "gold": gold, "platinum": plat, "diamond": diamond, "master": master}
                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent=4)
                await interaction.response.send_message(f"Rank roles: {bronze}, {silver}, {gold}, {plat}, {diamond}, {master} have been set.")


@client.tree.command(name="configqueuetext", description="Configure random text to go with queue/matchmaking") # 1.3 You can now submit empty entries to clear them and remove queuetext #
@app_commands.describe(digits = "How many digits of random numbers? (optional, 1-12)")
@app_commands.describe(lista = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listb = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listc = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listd = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(liste = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listf = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listg = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listh = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listi = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
@app_commands.describe(listj = "Input each entry to select from randomly, seperated by commas (,) (<- no space) (optional)")
async def configqueuetext(interaction: discord.Interaction, digits: int = None, lista: str = None, listb: str = None, listc: str = None, listd: str = None, liste: str = None, listf: str = None, listg: str = None, listh: str = None, listi: str = None, listj: str = None):
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if interaction.user.guild_permissions.manage_guild == True or interaction.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
        valid = True

    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 2:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in interaction.user.roles:
                    valid = True

    if valid == True:
        mystring = ""

        if "queuetext" not in database:
            database["queuetext"] = {}

        for y in range(10):
            x = y - 1
            variables = [lista, listb, listc, listd, liste, listf, listg, listh, listi, listj]
            strings = ["lista", "listb", "listc", "listd", "liste", "listf", "listg", "listh", "listi", "listj"]
            if variables[x]:
                if variables[x] == "null":
                    database["queuetext"][strings[x]] = None
                    mystring += f"Cleared list from database\n"
                else:
                    database["queuetext"][strings[x]] = variables[x]
                    mystring += f"Saved list to database\n"
            else:
                database["queuetext"][strings[x]] = None

        if digits:
            if digits > 12:
                digits = 12
            if digits < 1:
                digits = 1
            database["queuetext"]["digits"] = digits
            mystring += f"Added {digits} digit random number"
        else:
            database["queuetext"]["digits"] = None

        if mystring == "":
            mystring = "Queue text cleared"

        await interaction.response.send_message(mystring)

        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)


@client.tree.command(name="configmmrtype", description="PREMIUM FEATURE ~ Choose which type of mmr you want to be the server default") # 1.1 implemented check for purchase #
async def configmmrtype(interaction: discord.Interaction):
    user = interaction.user
    valid = False
    paid = False

    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 2:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if valid == True:
        async for x in client.entitlements(user=interaction.user):
            if x.sku_id == 1361516425172357320:
                paid = True
    
    if valid == False or paid == False:
        await interaction.response.send_message("You do not have permission to use this command. (This is a premium feature)", ephemeral=True)

    if valid == True and paid == True:
        await interaction.response.send_message("Choose which type of mmr you want to be the server default", view=MMRTypeButtons(interaction.guild.id, user.id, guildstring))


class MMRTypeButtons(discord.ui.View): # 1.1 red cancel button #
    def __init__(self, guildid, userid, guildstring):
        super().__init__(timeout=None)
        self.guildid = guildid
        self.userid = userid
        self.guildstring = guildstring

    @discord.ui.button(label="ZSR", style=discord.ButtonStyle.green)
    async def ChooseZSRButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.userid:
            guildname = str(interaction.guild.id)
            guildstring = guildname + ".json"
            with open(guildstring, 'r') as openfile:
                database = json.load(openfile)
            
            if "gamedata" not in database:
                database["gamedata"] = {}

            database["gamedata"]["mmrtype"] = "ZSR"
            with open(guildstring, "w") as outfile:
                json.dump(database, outfile, indent = 4)
            await interaction.response.edit_message(content="Set server mmr type to ZSR", view=None)

    @discord.ui.button(label="Elo", style=discord.ButtonStyle.green)
    async def ChooseEloButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.userid: 
            guildname = str(interaction.guild.id)
            guildstring = guildname + ".json"
            with open(guildstring, 'r') as openfile:
                database = json.load(openfile)
            
            if "gamedata" not in database:
                database["gamedata"] = {}

            database["gamedata"]["mmrtype"] = "Elo"
            with open(guildstring, "w") as outfile:
                json.dump(database, outfile, indent = 4)
            await interaction.response.edit_message(content="Set server mmr type to Elo", view=None)

    @discord.ui.button(label="TrueSkill", style=discord.ButtonStyle.green)
    async def ChooseTrueSkillButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.userid:
            guildname = str(interaction.guild.id)
            guildstring = guildname + ".json"
            with open(guildstring, 'r') as openfile:
                database = json.load(openfile)
            
            if "gamedata" not in database:
                database["gamedata"] = {}

            database["gamedata"]["mmrtype"] = "TrueSkill"
            with open(guildstring, "w") as outfile:
                json.dump(database, outfile, indent = 4)
            await interaction.response.edit_message(content="Set server mmr type to TrueSkill", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def ChooseCancelButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.userid:
            await interaction.response.edit_message(content="Canceled operation", view=None)


@client.tree.command(name="headtohead", description="Shows your head to head records") # Slash command 0.1
@app_commands.describe(myuser = "Which user would you like to see?")
async def headtohead(interaction: discord.Interaction, myuser: discord.User):
    userid = str(myuser.id)
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if userid not in database:
        await interaction.response.send_message(f"No h2h data found for {interaction.user.name}", ephemeral=True)
        return

    if userid in database:
        if "Head2Head" not in database[userid]:
            await interaction.response.send_message(f"No h2h data found for {interaction.user.name}", ephemeral=True)
            return

        await interaction.response.send_message(f"**{myuser.display_name}'s Head to Head Records:**\n", ephemeral=True)

        embed = discord.Embed()
        nametext = ""
        gametext = ""

        count = 0
        for x in database[userid]["Head2Head"]:
            try:
                tempuser = await interaction.guild.fetch_member(int(x))
                tempname = tempuser.display_name
            except:
                tempname = "-----"

            wins = database[userid]["Head2Head"][x][0]
            losses = database[userid]["Head2Head"][x][1]
            if wins + losses > 0:
                nametext += f"{tempname}\n"
                gametext += f"    {wins} / {losses}\n"
                count += 1

                if count >= 10:
                    embed.add_field(name="", value=nametext, inline=True)
                    embed.add_field(name="", value=gametext, inline=True)
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    embed = discord.Embed()
                    nametext = ""
                    gametext = ""
                    count = 0

        if count != 0:
            embed.add_field(name="", value=nametext, inline=True)
            embed.add_field(name="", value=gametext, inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)


@client.tree.command(name="newseason", description="Start a new ranked season with optional full or partial resets.") # 1.1 added history tracking #
async def newseason(interaction: discord.Interaction):
    user = interaction.user
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 3:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

        if valid == True:
            await interaction.response.send_message("", view=newseasonbuttons(user, guildstring))


class newseasonbuttons(discord.ui.View):
    def __init__(self, user, servername):
        super().__init__()
        self.user=user
        self.servername=servername

    @discord.ui.button(label="New season no reset", style=discord.ButtonStyle.blurple)
    async def NoResetButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.user == interaction.user:

            with open(self.servername, 'r') as openfile:
                database = json.load(openfile)

            if self.user.guild_permissions.manage_guild == True or self.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
                valid = True

            if "serverroles" in database:
                for x in database["serverroles"]:
                    if database["serverroles"][x] >= 3:
                        myrole = discord.utils.get(interaction.guild.roles, name=x)
                        if myrole in interaction.user.roles:
                            valid = True

            if valid == True:
                await interaction.response.edit_message(content="Season wins and losses reset to 0", view=None)

                sorteddb = dict(
                    sorted(
                        ((k, v) for k, v in database.items() if "mmr" in v),
                        key=lambda item: item[1]["mmr"],
                        reverse=True))

                for x in sorteddb:
                    database[x]["seasonwins"] = 0
                    database[x]["seasonlosses"] = 0

                    with open(self.servername, "w") as outfile:
                        json.dump(database, outfile, indent=4)

    @discord.ui.button(label="New season soft reset", style=discord.ButtonStyle.blurple)
    async def SoftResetButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.user == interaction.user:

            with open(self.servername, 'r') as openfile:
                database = json.load(openfile)

            if self.user.guild_permissions.manage_guild == True or self.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
                valid = True

            if "serverroles" in database:
                for x in database["serverroles"]:
                    if database["serverroles"][x] >= 3:
                        myrole = discord.utils.get(interaction.guild.roles, name=x)
                        if myrole in interaction.user.roles:
                            valid = True

            if valid == True:
                await interaction.response.edit_message(content="MMR halved, Elo set half way to default, uncertainty set half way to 1000, season wins and losses reset to 0", view=None)

                defaultelo = findstartingelo(self.servername)

                sorteddb = dict(
                    sorted(
                        ((k, v) for k, v in database.items() if "mmr" in v),
                        key=lambda item: item[1]["mmr"],
                        reverse=True))

                for x in sorteddb:
                    database[x]["mmr"] = math.ceil(database[x]["mmr"] / 2)

                    database[x]["uncertainty"] = math.ceil(database[x]["uncertainty"] / 2 + 500)

                    if "Elo" in database[x]:
                        database[x]["Elo"] = math.ceil((database[x]["Elo"] + defaultelo) / 2)

                    database[x]["seasonwins"] = 0
                    database[x]["seasonlosses"] = 0


                    if "zsrhistory" not in database[x]:
                        database[x]["zsrhistory"] = []
                    if "elohistory" not in database[x]:
                        database[x]["elohistory"] = []

                    database[x]["zsrhistory"].append(database[x]["mmr"])
                    if len(database[x]["zsrhistory"]) > 200:
                        database[x]["zsrhistory"] = database[x]["zsrhistory"][1:]

                    database[x]["elohistory"].append(database[x]["Elo"])
                    if len(database[x]["elohistory"]) > 200:
                        database[x]["elohistory"] = database[x]["elohistory"][1:]

                with open(self.servername, "w") as outfile:
                    json.dump(database, outfile, indent=4)

    @discord.ui.button(label="New season full reset", style=discord.ButtonStyle.blurple)
    async def FullResetButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.user == interaction.user:

            with open(self.servername, 'r') as openfile:
                database = json.load(openfile)

            if self.user.guild_permissions.manage_guild == True or self.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
                valid = True

            if "serverroles" in database:
                for x in database["serverroles"]:
                    if database["serverroles"][x] >= 3:
                        myrole = discord.utils.get(interaction.guild.roles, name=x)
                        if myrole in interaction.user.roles:
                            valid = True

            if valid == True:
                await interaction.response.edit_message(content="MMR set to 0, uncertainty set to 1000, Elo set to default, TrueSkill reset to 25/8.333, season wins and losses reset to 0", view=None)

                defaultelo = findstartingelo(self.servername)

                sorteddb = dict(
                    sorted(
                        ((k, v) for k, v in database.items() if "mmr" in v),
                        key=lambda item: item[1]["mmr"],
                        reverse=True))

                for x in sorteddb:
                    database[x]["mmr"] = 0

                    database[x]["uncertainty"] = 1000

                    database[x]["Elo"] = defaultelo

                    database[x]["seasonwins"] = 0
                    database[x]["seasonlosses"] = 0

                    database[x]["TrueSkillMu"] = 25
                    database[x]["TrueSkillSigma"] = 8.333

                    trueskilldelta = database[x]["TrueSkillMu"] - 3 * database[x]["TrueSkillSigma"]

                    if "zsrhistory" not in database[x]:
                        database[x]["zsrhistory"] = []
                    if "elohistory" not in database[x]:
                        database[x]["elohistory"] = []
                    if "tshistory" not in database[x]:
                        database[x]["tshistory"] = []

                    database[x]["zsrhistory"].append(database[x]["mmr"])
                    if len(database[x]["zsrhistory"]) > 200:
                        database[x]["zsrhistory"] = database[x]["zsrhistory"][1:]

                    database[x]["elohistory"].append(database[x]["Elo"])
                    if len(database[x]["elohistory"]) > 200:
                        database[x]["elohistory"] = database[x]["elohistory"][1:]

                    database[x]["tshistory"].append(trueskilldelta)
                    if len(database[x]["tshistory"]) > 200:
                        database[x]["tshistory"] = database[x]["tshistory"][1:]


                with open(self.servername, "w") as outfile:
                    json.dump(database, outfile, indent=4)


async def leaderboardtext(position, guildid, sorttype): # ver 1.06 fixed |* formatting #
    bigstring = "MMR Leaderboard:\n--------------------------------\n"
    leftstring = ""
    middlestring = ""
    rightstring = ""

    guild = client.get_guild(int(guildid))

    guildstring = guildid + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if sorttype.lower() == "zsr":
        sortstring = "mmr"
    if sorttype.lower() == "trueskill":
        sortstring = "TrueSkillDelta"
    if sorttype.lower() == "elo":
        sortstring = "Elo"

    # sorteddb = dict(sorted(
    # ((k, v) for k, v in database.items() if sortstring in v),
    # key=lambda item: item[1][sortstring], reverse=True))

    for x in database:
        if "TrueSkillMu" in database[x] and "TrueSkillSigma" in database[x]:
            database[x]["TrueSkillDelta"] = database[x]["TrueSkillMu"] - (3 * database[x]["TrueSkillSigma"])

    sorteddb = dict(
        sorted(((k, v)
        for k, v in database.items()
        if sortstring in v and v.get("wins", 0) > 0),
        key=lambda item: (item[1][sortstring], item[1]["wins"]),
        reverse=True))
            
    count = 1
    for user in sorteddb:
        target = guild.get_member(int(user))
        if target in guild.members: # TEST BOT CANT SEE SERVER MEMBERS FYI
            if "RankBan" not in database[user] or database[user]["RankBan"] == "False":
                try:
                    name = target.display_name
                except:
                    name = target.name
                # name = "name"

                wins = database[user]["wins"]
                loss = database[user]["losses"]
                
                if sorttype == "zsr":
                    mmr = database[user]["mmr"]
                if sorttype == "trueskill":
                    mmr = database[user]["TrueSkillDelta"]
                    mmr = round(mmr*10000)/10000
                if sorttype == "elo":
                    mmr = database[user]["Elo"]

                if "gamedata" not in database:
                    database["gamedata"] = {}
                if "mastertier" in database["gamedata"]:
                    tier2 = database["gamedata"]["silvertier"]
                    tier3 = database["gamedata"]["goldtier"]
                    tier4 = database["gamedata"]["platinumtier"]
                    tier5 = database["gamedata"]["diamondtier"]
                    tier6 = database["gamedata"]["mastertier"]
                else:
                    tier2 = 200
                    tier3 = 400
                    tier4 = 600
                    tier5 = 800
                    tier6 = 1000

                if "gamedata" in database:
                    if "mmrtype" in database["gamedata"]:
                        if database["gamedata"]["mmrtype"].lower() == "elo":
                            defaulttype = "elo"
                        elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                            defaulttype = "trueskill"
                        else:
                            defaulttype = "zsr"
                    else:
                        defaulttype = "zsr"
                else:
                    defaulttype = "zsr"

                if defaulttype == "zsr":
                    defaultmmr = database[user]["mmr"]
                if defaulttype == "trueskill":
                    defaultmmr = database[user]["TrueSkillDelta"]
                if defaulttype == "elo":
                    defaultmmr = database[user]["Elo"]

                emoji_1, emoji_2, emoji_3, emoji_4, emoji_5, emoji_6 = loademoji(guildstring)

                emoji = emoji_1
                if defaultmmr >= tier2:
                    emoji = emoji_2
                if defaultmmr >= tier3:
                    emoji = emoji_3
                if defaultmmr >= tier4:
                    emoji = emoji_4
                if defaultmmr >= tier5:
                    emoji = emoji_5
                if defaultmmr >= tier6:
                    emoji = emoji_6

                if position <= count <= position +19:
                    mmrstring = str(mmr)
                    stringlength = len(mmrstring)
                    adjust = 4 - stringlength
                    for x in range(adjust):
                        mmrstring = " " + mmrstring

                    string = str(f'{emoji} #{count} {mmrstring} - {name} - ({wins}/{loss})')
                    bigstring = bigstring + string + "\n"
                    string = str(f'{emoji} #{count}')
                    leftstring = leftstring + string + "\n"
                    string = str(f'{mmrstring}')
                    middlestring = middlestring + string + "\n"
                    string = str(f'{name} - ({wins}/{loss})')
                    rightstring = rightstring + string + "\n"
                count += 1

    bigstring = bigstring.replace("_", "\x5c_")
    bigstring = bigstring.replace("||", "\\||")
    bigstring = bigstring.replace("*", "\\*")
    bigstring = bigstring.replace("~~", "\\~~")

    rightstring = rightstring.replace("_", "\x5c_")
    rightstring = rightstring.replace("||", "\\||")
    rightstring = rightstring.replace("*", "\\*")
    rightstring = rightstring.replace("~~", "\\~~")

    # print(bigstring)

    return(bigstring, leftstring, middlestring, rightstring)


@client.tree.command(name="leaderboard", description="Show this server's leaderboard") # ver 1.03 added typing to remove error #
async def leaderboard(interaction: discord.Interaction):
    guildid = str(interaction.guild.id)
    if guildid != "704052660520878181" or str(interaction.user.id) == "215277233638604800":
        async with interaction.channel.typing():
            pass

        position = 1
        leftstring = ""
        middlestring = ""
        rightstring = ""

        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)
        
        if "gamedata" in database:
            if "mmrtype" in database["gamedata"]:
                if database["gamedata"]["mmrtype"].lower() == "elo":
                    sorttype = "elo"
                elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                    sorttype = "trueskill"
                else:
                    sorttype = "zsr"
            else:
                sorttype = "zsr"
        else:
            sorttype = "zsr"

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(position, guildid, sorttype)
        ############################

        desctext = "MMR Leaderboard"
        embed = discord.Embed(
            # description = desctext,
            title = "MMR Leaderboard"
        )
        embed.add_field(name="", value=leftstring, inline=True)
        embed.add_field(name="", value=middlestring, inline=True)
        embed.add_field(name="", value=rightstring, inline=True)

        await interaction.response.send_message(embed=embed, view=LeaderboardButtons(position, sorttype))


class LeaderboardButtons(discord.ui.View):
    def __init__(self, position, sorttype):
        super().__init__(timeout=None)
        self.position=position
        self.sorttype=sorttype

    @discord.ui.button(label="Previous", custom_id="previousbutton", style=discord.ButtonStyle.blurple)
    async def PreviousButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position -= 20
        if self.position < 1:
            self.position = 1

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        embed = discord.Embed(
            title = "MMR Leaderboard"
        )
        embed.add_field(name="", value=leftstring, inline=True)
        embed.add_field(name="", value=middlestring, inline=True)
        embed.add_field(name="", value=rightstring, inline=True)

        await interaction.response.edit_message(embed=embed, view=LeaderboardButtons(self.position, self.sorttype))


    @discord.ui.button(label="Next", custom_id="nextbutton", style=discord.ButtonStyle.blurple)
    async def NextButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position += 20

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        embed = discord.Embed(
            title = "MMR Leaderboard"
        )
        embed.add_field(name="", value=leftstring, inline=True)
        embed.add_field(name="", value=middlestring, inline=True)
        embed.add_field(name="", value=rightstring, inline=True)

        await interaction.response.edit_message(embed=embed, view=LeaderboardButtons(self.position, self.sorttype))


    @discord.ui.button(label="Sort by ZSR", custom_id="showzsr", style=discord.ButtonStyle.green)
    async def showzsrButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = 1
        self.sorttype = "zsr"

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        embed = discord.Embed(
            title = "MMR Leaderboard"
        )
        embed.add_field(name="", value=leftstring, inline=True)
        embed.add_field(name="", value=middlestring, inline=True)
        embed.add_field(name="", value=rightstring, inline=True)

        await interaction.response.edit_message(embed=embed, view=LeaderboardButtons(self.position, self.sorttype))


    @discord.ui.button(label="Sort by Elo", custom_id="showelo", style=discord.ButtonStyle.green)
    async def showeloButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = 1
        self.sorttype = "elo"

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        embed = discord.Embed(
            title = "MMR Leaderboard"
        )
        embed.add_field(name="", value=leftstring, inline=True)
        embed.add_field(name="", value=middlestring, inline=True)
        embed.add_field(name="", value=rightstring, inline=True)

        await interaction.response.edit_message(embed=embed, view=LeaderboardButtons(self.position, self.sorttype))


    @discord.ui.button(label="Sort by TrueSkill", custom_id="showtrueskill", style=discord.ButtonStyle.green)
    async def showtrueskillButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = 1
        self.sorttype = "trueskill"

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        embed = discord.Embed(
            title = "MMR Leaderboard"
        )
        embed.add_field(name="", value=leftstring, inline=True)
        embed.add_field(name="", value=middlestring, inline=True)
        embed.add_field(name="", value=rightstring, inline=True)

        await interaction.response.edit_message(embed=embed, view=LeaderboardButtons(self.position, self.sorttype))


@client.tree.command(name="oldleaderboard", description="Show this server's leaderboard (in plain text)") # ver 1.03 added typing to remove error #
async def oldleaderboard(interaction: discord.Interaction):
    position = 1
    bigstring = ""
    leftstring = ""
    middlestring = ""
    rightstring = ""
    count = 1
    guildid = str(interaction.guild.id)
    
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)
    
    if "gamedata" in database:
        if "mmrtype" in database["gamedata"]:
            if database["gamedata"]["mmrtype"].lower() == "elo":
                sorttype = "elo"
            elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                sorttype = "trueskill"
            else:
                sorttype = "zsr"
        else:
            sorttype = "zsr"
    else:
        sorttype = "zsr"

    ############################
    bigstring, leftstring, middlestring, rightstring = await leaderboardtext(position, guildid, sorttype)
    ############################

    # await interaction.response.send_message(f"MMR Leaderboard:\n--------------------------------")
    await interaction.response.send_message(f"{bigstring}", view=OLBButtons(position, sorttype))


class OLBButtons(discord.ui.View):
    def __init__(self, position, sorttype):
        super().__init__(timeout=None)
        self.position=position
        self.sorttype=sorttype

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def PreviousButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position -= 20
        if self.position < 0:
            self.position = 1

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        await interaction.response.edit_message(content=f"{bigstring}")


    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def NextButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position += 20

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        await interaction.response.edit_message(content=f"{bigstring}")


    @discord.ui.button(label="Sort by ZSR", custom_id="showzsr", style=discord.ButtonStyle.green)
    async def showzsrButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = 1
        self.sorttype = "zsr"

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        await interaction.response.edit_message(content=f"{bigstring}")


    @discord.ui.button(label="Sort by Elo", custom_id="showelo", style=discord.ButtonStyle.green)
    async def showeloButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = 1
        self.sorttype = "elo"

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        await interaction.response.edit_message(content=f"{bigstring}")


    @discord.ui.button(label="Sort by TrueSkill", custom_id="showtrueskill", style=discord.ButtonStyle.green)
    async def showtrueskillButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = 1
        self.sorttype = "trueskill"

        guildname = str(interaction.guild.id)

        guildid = str(interaction.guild.id)

        ############################
        bigstring, leftstring, middlestring, rightstring = await leaderboardtext(self.position, guildid, self.sorttype)
        ############################

        await interaction.response.edit_message(content=f"{bigstring}")


@client.tree.command(name="undorank", description="Undoes the most recent game for a user") # 1.1 allows multiple users # 
@app_commands.describe(user1 = "Which user would you like to undo their last game?")
@app_commands.describe(user2 = "Which user would you like to undo their last game?")
@app_commands.describe(user3 = "Which user would you like to undo their last game?")
@app_commands.describe(user4 = "Which user would you like to undo their last game?")
@app_commands.describe(user5 = "Which user would you like to undo their last game?")
@app_commands.describe(user6 = "Which user would you like to undo their last game?")
@app_commands.describe(user7 = "Which user would you like to undo their last game?")
@app_commands.describe(user8 = "Which user would you like to undo their last game?")
@app_commands.describe(user9 = "Which user would you like to undo their last game?")
@app_commands.describe(user0 = "Which user would you like to undo their last game?")
async def undorank(interaction: discord.Interaction, user1: discord.User, user2: discord.User = None, user3: discord.User = None, user4: discord.User = None, user5: discord.User = None, user6: discord.User = None, user7: discord.User = None, user8: discord.User = None, user9: discord.User = None, user0: discord.User = None):
    user = interaction.user
    
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)
    undostring = guildname + "undo.json"
    with open(undostring, 'r') as openfile:
        undodatabase = json.load(openfile)

    if "serverroles" not in database:
        database["serverroles"] = {}

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    for x in database["serverroles"]:
        if database["serverroles"][x] >= 1:
            myrole = discord.utils.get(interaction.guild.roles, name=x)
            if myrole in user.roles:
                valid = True

    if valid == True:
        successstring = "Last game undone for: "
        for x in [user0, user1, user2, user3, user4, user5, user6, user7, user8, user9]:
            if x is not None:
                tempid = str(x.id)
                if tempid in undodatabase:
                    database[tempid] = undodatabase[tempid]
                    name = x.name
                    successstring += f"{name}, "
                    print(f"undid {name}")

                else:
                    await interaction.response.send_message(f"Error: target not in undo database", ephemeral=True)
                    return

        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)
        await interaction.channel.send(successstring[:-2])
        await interaction.channel.send("Note: This command only remembers one game per user. Run this command for each teammate/opponent as necessary. Undo database does not save 'set' commands.")

        
    else:
        await interaction.response.send_message(f"You dont have permission to use this command", ephemeral=True)


@client.tree.command(name="server", description="Show some info about this server") # Slash command 0.1
async def server(interaction: discord.Interaction):
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    sorteddb = dict(
        sorted(
            ((k, v) for k, v in database.items() if "mmr" in v),
            key=lambda item: item[1]["mmr"],
            reverse=True))

    totalgames = 0
    countusers = 0

    for x in sorteddb:
        totalgames += database[x]["wins"]
        countusers += 1

    summmr = 0
    sumusers = 0
    for x in sorteddb:
        if database[x]["wins"] + database[x]["losses"] >= 20:
            summmr += database[x]["mmr"]
            sumusers += 1

    sumusers = max(sumusers, 1)
    avgmmr = math.ceil(summmr / sumusers)

    serveraveragemmr = 0
    totalmmr = 0
    totalusers = 0

    sorteddb = dict(
        sorted(
            ((k, v) for k, v in database.items() if "mmr" in v),
            key=lambda item: item[1]["mmr"],
            reverse=True))

    for x in sorteddb:
        if database[x]["uncertainty"] < 500:
            totalmmr += database[x]["mmr"]
            totalusers += 1

    if totalusers > 0:
        serveraveragemmr = math.ceil(totalmmr / totalusers)

    if totalusers == 0 or serveraveragemmr < 100:
        adjustedmmr = 100
    else:
        adjustedmmr = serveraveragemmr

    if "season" in database["gamedata"]:
        currentseason = database["gamedata"]["season"]
    else:
        currentseason = 0

    await interaction.response.send_message(f"**{guildname}**:\nTotal users: {countusers}\nTotal games played: {totalgames}\nUsers >=20 games: {sumusers}\nAverage MMR <500 Uncertainty: {serveraveragemmr}\nAdjusted avg mmr: {adjustedmmr}\nCurrent Season: {currentseason}")


async def showtextbase(userid, database, guild): # 1.4.4.2 fixed color on no change #
    guildstring = str(guild.id) + ".json"

    if "gamedata" in database:
        if "mmrtype" in database["gamedata"]:
            if database["gamedata"]["mmrtype"].lower() == "elo":
                sorttype = "elo"
            elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                sorttype = "trueskill"
            else:
                sorttype = "zsr"
        else:
            sorttype = "zsr"
    else:
        sorttype = "zsr"

    if userid in database:
        try:
            myuser = await guild.fetch_member(userid)
        except:
            myuser = await client.fetch_user(userid)

        try:
            name = myuser.display_name
        except:
            name = myuser.name

        name = name.replace("_", "\x5c_")
        name = name.replace("||", "\\||")
        name = name.replace("*", "\\*")
        name = name.replace("~~", "\\~~")

        mymmr = database[userid]["mmr"]
        wins = database[userid]["wins"]
        loss = database[userid]["losses"]
        uncertain = database[userid]["uncertainty"]
        streak = database[userid]["streak"]
        if "Elo" not in database[userid]:
            database[userid]["Elo"] = 1000
        elo = database[userid]["Elo"]
        if "TrueSkillMu" not in database[userid]:
            database[userid]["TrueSkillMu"] = 25
        if "TrueSkillSigma" not in database[userid]:
            database[userid]["TrueSkillSigma"] = 8.333
        trueskillmu = database[userid]["TrueSkillMu"]
        trueskillsigma = database[userid]["TrueSkillSigma"]
        trueskilldelta = trueskillmu - 3 * trueskillsigma
        if "seasonwins" not in database[userid]:
            database[userid]["seasonwins"] = wins
        seasonwins = database[userid]["seasonwins"]
        if "seasonlosses" not in database[userid]:
            database[userid]["seasonlosses"] = loss
        seasonlosses = database[userid]["seasonlosses"]

        try:
            peakZSR = database[userid]["peakzsr"]
            peakElo = database[userid]["peakelo"]
            peakTS = database[userid]["peakts"]
        except:
            peakZSR, peakElo, peakTS = mymmr, elo, trueskilldelta

        

        trueskillmu = round(trueskillmu * 1000)/1000
        trueskillsigma = round(trueskillsigma * 1000)/1000
        trueskilldelta = round(trueskilldelta * 1000)/1000
        peakTS = round(peakTS * 1000)/1000

        if "gamedata" not in database:
            database["gamedata"] = {}
        if "mastertier" in database["gamedata"]:
            tier2 = database["gamedata"]["silvertier"]
            tier3 = database["gamedata"]["goldtier"]
            tier4 = database["gamedata"]["platinumtier"]
            tier5 = database["gamedata"]["diamondtier"]
            tier6 = database["gamedata"]["mastertier"]
        else:
            tier2 = 200
            tier3 = 400
            tier4 = 600
            tier5 = 800
            tier6 = 1000

        if "gamedata" in database:
            if "mmrtype" in database["gamedata"]:
                if database["gamedata"]["mmrtype"].lower() == "elo":
                    defaulttype = "elo"
                elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                    defaulttype = "trueskill"
                else:
                    defaulttype = "zsr"
            else:
                defaulttype = "zsr"
        else:
            defaulttype = "zsr"

        if defaulttype == "zsr":
            defaultmmr = database[userid]["mmr"]
        if defaulttype == "trueskill":
            defaultmmr = database[userid]["TrueSkillMu"] - (3 * database[userid]["TrueSkillSigma"])
        if defaulttype == "elo":
            defaultmmr = database[userid]["Elo"]

        emoji_1, emoji_2, emoji_3, emoji_4, emoji_5, emoji_6 = loademoji(guildstring)

        emoji = emoji_1
        if defaultmmr >= tier2:
            emoji = emoji_2
        if defaultmmr >= tier3:
            emoji = emoji_3
        if defaultmmr >= tier4:
            emoji = emoji_4
        if defaultmmr >= tier5:
            emoji = emoji_5
        if defaultmmr >= tier6:
            emoji = emoji_6

        if sorttype.lower() == "zsr":
            sortstring = "mmr"
        if sorttype.lower() == "trueskill":
            sortstring = "TrueSkillDelta"
        if sorttype.lower() == "elo":
            sortstring = "Elo"

        for x in database:
            if "TrueSkillMu" in database[x] and "TrueSkillSigma" in database[x]:
                database[x]["TrueSkillDelta"] = database[x]["TrueSkillMu"] - (3 * database[x]["TrueSkillSigma"])

        sorteddb = dict(
                sorted(((k, v)
                for k, v in database.items()
                if sortstring in v and v.get("wins", 0) > 0),
                key=lambda item: (item[1][sortstring], item[1]["wins"]),
                reverse=True))
        
        serverhighest = 0
        for x in sorteddb:
            if "TrueSkillMu" in sorteddb[x] and "TrueSkillSigma" in sorteddb[x]:
                sorteddb[x]["TrueSkillDelta"] = sorteddb[x]["TrueSkillMu"] - (3 * sorteddb[x]["TrueSkillSigma"])

            if sorteddb[x][sortstring] > serverhighest:
                serverhighest = sorteddb[x][sortstring]

        count = 0
        myposition = 0
        for x in sorteddb:
            mmr = database[x][sortstring]
            if mmr > 0:
                count += 1
                if str(x) == userid:
                    myposition = count

        if wins + loss != 0:
            winrate = 1000*wins/(wins+loss)
            winrate = round(winrate) / 10
        else:
            winrate = 0

        embed = discord.Embed(
            title = name
        )

        mytext = f'{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}\nPosition: {myposition}\nWin/Loss: {wins} / {loss}\nSeason win/loss: {seasonwins} / {seasonlosses}\nWinrate: {winrate}%\nStreak: {streak}\n\n**ZSR:**\nMMR: {mymmr}\nPeak: {peakZSR}\nUncertainty: {uncertain}\n\n**Elo:**\nRank: {elo}\nPeak: {peakElo}\n\n**TrueSkill:**\nDelta: {trueskilldelta}\nPeak: {peakTS}\nMu: {trueskillmu}\nSigma: {trueskillsigma}\n{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}'
        embed.add_field(name="", value=mytext)

        if sorttype.lower() == "zsr":
            sortstring = "peakzsr"
        if sorttype.lower() == "trueskill":
            sortstring = "peakts"
        if sorttype.lower() == "elo":
            sortstring = "peakelo"

        userpeak = 0
        if "peakzsr" in database[userid]:
            userpeak = database[userid][sortstring]

            if sorttype.lower() == "zsr":
                sortstring = "zsrhistory"
            if sorttype.lower() == "trueskill":
                sortstring = "tshistory"
            if sorttype.lower() == "elo":
                sortstring = "elohistory"

            red = (255,0,0)
            blue = (0,0,255)
            yellow = (255,255,0)
            green = (0,255,0)
            orange = (255,127,0)
            purple = (255,0,255)
            white = (255,255,255)
            lightgray = (190,190,190)
            gray = (127,127,127)
            darkgray = (63,63,63)
            black = (0,0,0)

            backgroundcolor = (25,25,25)
            wincolor = (0,127,255)
            losscolor = (255,63,0)

            img = Image.new("RGB", (800,400), backgroundcolor)
            draw = ImageDraw.Draw(img)

            markA = 50
            markB = 100
            markC = 200
            markD = 300
            markE = 400
            markF = 500
            markG = 1000
            markH = 2000
            markI = 3000

            tier2 = 200
            tier3 = 400
            tier4 = 600
            tier5 = 800
            tier6 = 1000

            if "gamedata" in database:
                if "mastertier" in database["gamedata"]:
                    tier2 = database["gamedata"]["silvertier"]
                    tier3 = database["gamedata"]["goldtier"]
                    tier4 = database["gamedata"]["platinumtier"]
                    tier5 = database["gamedata"]["diamondtier"]
                    tier6 = database["gamedata"]["mastertier"]

            imagescale = max(((max(serverhighest, userpeak) + 100) / 400), 0.2)

            displayserverhighest = serverhighest / imagescale
            displayuserpeak = userpeak / imagescale

            scores = database[userid][sortstring]
            for x in range(len(scores)):
                scores[x] /= imagescale

            tier2 /= imagescale
            tier3 /= imagescale
            tier4 /= imagescale
            tier5 /= imagescale
            tier6 /= imagescale

            markA /= imagescale
            markB /= imagescale
            markC /= imagescale
            markD /= imagescale
            markE /= imagescale
            markF /= imagescale
            markG /= imagescale
            markH /= imagescale
            markI /= imagescale

            draw.line(((0, 400-displayserverhighest), (800, 400-displayserverhighest)), fill=orange)
            draw.line(((0, 400-displayuserpeak), (800, 400-displayuserpeak)), fill=white)

            draw.line(((0, 400-markA), (20, 400-markA)), fill=gray)
            draw.line(((0, 400-markB), (20, 400-markB)), fill=gray)
            draw.line(((0, 400-markC), (20, 400-markC)), fill=gray)
            draw.line(((0, 400-markD), (20, 400-markD)), fill=gray)
            draw.line(((0, 400-markE), (20, 400-markE)), fill=gray)
            draw.line(((0, 400-markF), (20, 400-markF)), fill=gray)
            draw.line(((0, 400-markG), (20, 400-markG)), fill=gray)
            draw.line(((0, 400-markH), (20, 400-markH)), fill=gray)
            draw.line(((0, 400-markI), (20, 400-markI)), fill=gray)

            draw.line(((770, 400-tier2), (800, 400-tier2)), fill=gray)
            draw.line(((770, 400-tier3), (800, 400-tier3)), fill=gray)
            draw.line(((770, 400-tier4), (800, 400-tier4)), fill=gray)
            draw.line(((770, 400-tier5), (800, 400-tier5)), fill=gray)
            draw.line(((770, 400-tier6), (800, 400-tier6)), fill=gray)

            draw.text((750, 386-tier2), "Silver", fill=(255, 255, 255, 255))
            draw.text((750, 386-tier3), "Gold", fill=(255, 255, 0, 255))
            draw.text((750, 386-tier4), "Platinum", fill=(0, 255, 128, 255))
            draw.text((750, 386-tier5), "Diamond", fill=(0, 128, 255, 255))
            draw.text((750, 386-tier6), "Master", fill=(255, 63, 0, 255))

            draw.text((0, 386-markA), "50", fill=(255, 255, 255, 255))
            draw.text((0, 386-markB), "100", fill=(255, 255, 255, 255))
            draw.text((0, 386-markC), "200", fill=(255, 255, 255, 255))
            draw.text((0, 386-markD), "300", fill=(255, 255, 255, 255))
            draw.text((0, 386-markE), "400", fill=(255, 255, 255, 255))
            draw.text((0, 386-markF), "500", fill=(255, 255, 255, 255))
            draw.text((0, 386-markG), "1000", fill=(255, 255, 255, 255))
            draw.text((0, 386-markH), "2000", fill=(255, 255, 255, 255))
            draw.text((0, 386-markI), "3000", fill=(255, 255, 255, 255))

            draw.text((6, 6), name, fill=(255, 255, 255, 255))
            draw.text((6, 20), guild.name, fill=(255, 255, 255, 255))

            draw.text((210, 386-displayserverhighest), f"Server Highest: {round(serverhighest, 1)}", fill=(255, 255, 255, 255))
            draw.text((90, 386-displayuserpeak), f"My Peak: {round(userpeak, 1)}", fill=(255, 255, 255, 255))


            for x in range(len(scores)-1):
                firstpoint = 400 - scores[x]
                secondpoint = 400 - scores[x+1]

                lengthscale = clamp(800/len(scores), 4, 25)

                timeline1 = x * lengthscale
                timeline2 = (x + 1) * lengthscale

                linecolor = wincolor
                if scores[x] >= scores[x+1]:
                    linecolor = losscolor
                draw.line(((timeline1, firstpoint-1), (timeline2, secondpoint-1)), fill=linecolor)
                draw.line(((timeline1, firstpoint), (timeline2, secondpoint)), fill=linecolor)
                draw.line(((timeline1, firstpoint+1), (timeline2, secondpoint+1)), fill=linecolor)

            with io.BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)

                mychannel = await client.fetch_channel(1353033947663175760)
                imagemessage = await mychannel.send(file=discord.File(fp=image_binary, filename='img.png'))
                myurl = imagemessage.attachments[0].url
                embed.set_image(url=myurl)

                # embed.set_image(url="img.png")
            

        return embed#, img

        # text = (f'{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}\n{name}\nPosition: {myposition}\nWin/Loss: {wins} / {loss}\nSeason win/loss: {seasonwins} / {seasonlosses}\nWinrate: {winrate}%\nStreak: {streak}\n**ZSR:**\nMMR: {mymmr}\nPeak: {peakZSR}\nUncertainty: {uncertain}\n**Elo:**\nRank: {elo}\nPeak: {peakElo}\n**TrueSkill:**\nDelta: {trueskilldelta}\nPeak: {peakTS}\nMu: {trueskillmu}\nSigma: {trueskillsigma}\n{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}{emoji}')
        # return text


@client.tree.command(name="showme", description="Show your detailed stats") # 1.5 shows users without games #
async def showme(interaction: discord.Interaction):
    userid = str(interaction.user.id)
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if userid not in database:
        database[userid] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}

    showtext = await showtextbase(userid, database, interaction.guild)
    mymessage = await interaction.response.send_message(embed=showtext)


@client.tree.command(name="show", description="Show detailed stats of another user") # 1.5 shows users without games #
@app_commands.describe(myuser = "Which user would you like to see?")
async def show(interaction: discord.Interaction, myuser: discord.User):
    userid = str(myuser.id)
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if userid not in database:
        database[userid] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}

    showtext = await showtextbase(userid, database, interaction.guild)
    mymessage = await interaction.response.send_message(embed=showtext)


@client.tree.command(name="forcewin", description="Submit a game with winners and losers and force submit the results") # 1.0 #
async def forcewin(interaction: discord.Interaction):
    user = interaction.user
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)
    
    if "serverroles" not in database:
        database["serverroles"] = {}

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    for x in database["serverroles"]:
        if database["serverroles"][x] >= 1:
            myrole = discord.utils.get(interaction.guild.roles, name=x)
            if myrole in user.roles:
                valid = True


    if valid == True:

        winners = []
        losers = []

        await interaction.response.send_message("Select winners, then losers", view=forcewinuserselect(winners, losers), ephemeral=True)


class forcewinuserselect(discord.ui.View): # 1.1 uses embeds #
    def __init__(self, winners, losers):
        super().__init__(timeout=None)
        self.winners = []
        self.losers = []

    @discord.ui.select(max_values=25, min_values=1, cls=discord.ui.UserSelect)
    async def selectwinners(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.winners = select.values 
        
        printedlist = []
        for x in self.winners:
            printedlist.append(str(x.id))
        
        await interaction.response.defer(ephemeral=True)
       

    @discord.ui.select(max_values=25, min_values=1, cls=discord.ui.UserSelect)
    async def selectlosers(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.losers = select.values 
        
        printedlist = []
        for x in self.losers:
            printedlist.append(str(x.id))
        
        await interaction.response.defer(ephemeral=True)

    
    @discord.ui.button(label="Submit", style=discord.ButtonStyle.blurple)
    async def SubmitButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        valid = True
        winnerlist = []
        loserlist = []

        for x in self.winners:
            winnerlist.append(str(x.id))
        for x in self.losers:
            loserlist.append(str(x.id))

        guildid = str(interaction.guild.id)
        guildstring = guildid + ".json"
        undostring = guildid + "undo.json"

        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        members = winnerlist + loserlist
        for x in members:
            if x not in database:
                database[x] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent = 4)
            if "RankBan" in database[x]:
                if database[x]["RankBan"] == "True":
                    valid = False
                    await interaction.followup.send("Game not submitted. One or more players is restricted from playing ranked.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()

        if valid == True:
            embed = await rankcalc(interaction, winnerlist, loserlist, guildstring, undostring)
            await interaction.channel.send(embed=embed, view=None)
        

@client.tree.command(name="idwin", description="Submit a game with winners and losers using their discord id and force submit the results") # 1.1 uses embeds #
@app_commands.describe(winnertext = "input the id(s) of the winner(s) seperated by spaces")
@app_commands.describe(losertext = "input the id(s) of the winner(s) seperated by spaces")
async def idwin(interaction: discord.Interaction, winnertext: str, losertext: str):
    user = interaction.user
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    undostring = guildname + "undo.json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    errorstring = ""
    valid = False
    
    if "serverroles" not in database:
        database["serverroles"] = {}

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    for x in database["serverroles"]:
        if database["serverroles"][x] >= 1:
            myrole = discord.utils.get(interaction.guild.roles, name=x)
            if myrole in user.roles:
                valid = True

    if valid == True:
        winners = winnertext.split()
        losers = losertext.split()

        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        members = winners + losers
        for x in members:
            if not all(char in "0123456789" for char in x):
                valid = False
                errorstring = "Game not submitted. One or more IDs are invalid."
            
        if valid == True:
            for x in members:
                if x not in database:
                    database[x] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
                    with open(guildstring, "w") as outfile:
                        json.dump(database, outfile, indent = 4)
                if "RankBan" in database[x]:
                    if database[x]["RankBan"] == "True":
                        valid = False
                        errorstring = errorstring + "\nGame not submitted. One or more players is restricted from playing ranked."

            if valid == True:
                if len(winners) >= 1 and len(losers) >= 1:
                    embed = await rankcalc(interaction, winners, losers, guildstring, undostring)
                    await interaction.channel.send(embed=embed, view=None)
                
                else:
                    errorstring = errorstring + "\nGame not submitted. You need at least one winner and loser."
                    valid = False

    if valid == False:
        await interaction.response.send_message(errorstring, ephemeral=True)


@client.tree.command(name="win", description="Submit a game with winners and losers") # Slash command 0.1
async def win(interaction: discord.Interaction):
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)
        
    winners = []
    losers = []

    await interaction.response.send_message("Select winners, then losers:", view=winuserselect(winners, losers), ephemeral=True)


class winuserselect(discord.ui.View): # 1.1 uses embeds #
    def __init__(self, winners, losers):
        super().__init__(timeout=None)
        self.winners = []
        self.losers = []

    @discord.ui.select(max_values=25, min_values=1, cls=discord.ui.UserSelect)
    async def aselectwinners(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.winners = select.values 
        
        printedlist = []
        for x in self.winners:
            printedlist.append(str(x.id))
        
        await interaction.response.defer(ephemeral=True)


    @discord.ui.select(max_values=25, min_values=1, cls=discord.ui.UserSelect)
    async def aselectlosers(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.losers = select.values 
        
        printedlist = []
        for x in self.losers:
            printedlist.append(str(x.id))
        
        await interaction.response.defer(ephemeral=True)

    
    @discord.ui.button(label="Submit", style=discord.ButtonStyle.blurple)
    async def aSubmitButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        winnerlist = []
        loserlist = []
        valid = True
        await interaction.response.defer(ephemeral=True)

        for x in self.winners:
            winnerlist.append(str(x.id))
        for x in self.losers:
            loserlist.append(str(x.id))

        guildid = str(interaction.guild.id)
        guildstring = guildid + ".json"
        undostring = guildid + "undo.json"

        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        members = winnerlist + loserlist
        for x in members:
            if x not in database:
                database[x] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
                with open(guildstring, "w") as outfile:
                    json.dump(database, outfile, indent = 4)
            if "RankBan" in database[x]:
                if database[x]["RankBan"] == "True":
                    valid = False
                    await interaction.followup.send("Game not submitted. One or more players is restricted from playing ranked.", ephemeral=True)

        for x in winnerlist:
            if x in loserlist:
                valid = False
                await interaction.followup.send("Game not submitted. Someone marked as a winner and loser.", ephemeral=True)

        if len(winnerlist) == 0 or len(loserlist) == 0:
            valid = False
            await interaction.followup.send("Game not submitted. You need at least one winner and loser.", ephemeral=True)

        if str(interaction.user.id) not in winnerlist and str(interaction.user.id) not in loserlist:
            valid = False
            await interaction.followup.send("Game not submitted. Game must be submitted by one of the players.", ephemeral=True)

        await interaction.delete_original_response()

        if valid == True:
            firstwinner = self.winners[0]
            winnername = firstwinner.display_name

            username = interaction.user.display_name
            if interaction.user in self.winners:
                oppteam = loserlist
                oppname = str(await interaction.guild.fetch_member(loserlist[0]))
            if interaction.user in self.losers:
                oppteam = winnerlist
                oppname = str(await interaction.guild.fetch_member(winnerlist[0]))

            winneratstring = ""
            for x in winnerlist:
                winneratstring = winneratstring + "<@" + x + "> "

            loseratstring = ""
            for x in loserlist:
                loseratstring = loseratstring + "<@" + x + "> "



            tempstring = "Match reported!\nIt is reported that\n" + winneratstring + "\nwon against\n" + loseratstring + "\n" + oppname + "'s team, do you confirm this result?"
            tempstring = tempstring.replace("_", "\x5c_")
            await interaction.channel.send(tempstring, view=ReportButtons("empty", oppteam, winnerlist, loserlist, guildstring, undostring))
        
        
class ReportButtons(discord.ui.View):
    def __init__(self, response, oppteam, winners, losers, guildstring, undostring):
        super().__init__(timeout=None)
        self.response=response
        self.oppteam=oppteam
        self.winners=winners
        self.losers=losers
        self.guildstring=guildstring
        self.undostring=undostring

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green)
    async def YesButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.oppteam:
            if self.response == "empty":
                self.response = "Yes"
                embed = await rankcalc(interaction, self.winners, self.losers, self.guildstring, self.undostring)
                await interaction.response.edit_message(embed=embed, content=None, view=None)
        if str(interaction.user.id) not in self.oppteam:
            pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def NoButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.winners or str(interaction.user.id) in self.losers:
            if self.response == "empty":
                self.response = "No"
                winnernames = []
                losernames = []
                for x in self.winners:
                    y = await interaction.guild.fetch_member(x)
                    winnernames.append(y.name)
                for x in self.losers:
                    y = await interaction.guild.fetch_member(x)
                    losernames.append(y.name)
                string = (f"Match {winnernames} vs {losernames} rejected by {interaction.user}")
                await interaction.response.edit_message(content=string, view=None)

    @discord.ui.button(label="Staff Override: Cancel", style=discord.ButtonStyle.gray)
    async def OverrideAButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        valid = False

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 1:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in interaction.message.author.roles:
                        valid = True

        if interaction.user.guild_permissions.manage_guild == True or interaction.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
            valid = True

        if valid==True:
            if self.response == "empty":
                self.response = "No"
                winnernames = []
                losernames = []
                for x in self.winners:
                    y = await interaction.guild.fetch_member(x)
                    winnernames.append(y.name)
                for x in self.losers:
                    y = await interaction.guild.fetch_member(x)
                    losernames.append(y.name)
                string = (f"Match {winnernames} vs {losernames} rejected by {interaction.user}")
                await interaction.response.edit_message(content=string, view=None)


@client.tree.command(name="queue", description="Start a matchmaking queue") # 1.3 send message as response to avoid error #
@app_commands.describe(size = "how many players per game?")
@app_commands.describe(sbmm = "True = Enable skill based matchmaking / False = Full random matchmaking")
async def queue(interaction: discord.Interaction, size: int, sbmm: bool):
    user = interaction.user
    range = "None"
    number = 1
    valid = False
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if valid == True:
        userlist = {}
        if size % 2 != 0 or size < 2 or size > 20:
            valid = False
            await interaction.response.send_message(f"Size must be an even number from 2 to 20", ephemeral=True)

        if valid == True:
            await interaction.response.send_message(f"<a:rgb:1319062935057727511>**Queue:** *(size: {size})* *(Members in queue: **{len(userlist)}**) (SBMM: {sbmm})*<a:rgb:1319062935057727511>", view=NewQueueButtons(size, range, userlist, number, sbmm))


class NewQueueButtons(discord.ui.View): # 1.3 Added SBMM toggle, fixed glitches
    def __init__(self, size, range, userlist, number, sbmm):
        super().__init__(timeout=None)
        self.size = size
        self.range = range
        self.userlist = userlist
        self.number = number
        self.sbmm = sbmm

    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.green)
    async def NewJoinQueueButton(self, interaction: discord.Interaction, button: discord.ui.Button):

        # queuebutton = interaction.message
        # mymessage = await interaction.channel.fetch_message(queuebutton.id)

        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        undostring = str(interaction.guild.id) + "undo" + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        newuser = interaction.user
        newid = str(newuser.id)

        if newid not in database:
            database[newid] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000, "Elo": findstartingelo(guildstring), "TrueSkillMu": 25, "TrueSkillSigma": 8.333}

        if newid in database:
            if "streak" not in database[newid]:
                database[newid]["streak"] = 0
            if "uncertainty" not in database[newid]:
                database[newid]["uncertainty"] = 1000

        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)

        if "RankBan" in database[newid]:
            if database[newid]["RankBan"] == "True":
                await interaction.response.send_message(content="You are banned from queue and cannot join", ephemeral=True)

        if "RankBan" not in database[newid] or database[newid]["RankBan"] == "False":
            if newid not in self.userlist:
                
                mymmr = database[newid]["mmr"] + (database[newid]["uncertainty"] / 10)
                if "gamedata" in database:
                    if "mmrtype" in database["gamedata"]:
                        if database["gamedata"]["mmrtype"].lower() == "elo":
                            mymmr = database[newid]["Elo"]
                        elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                            mymmr = (database[newid]["TrueSkillMu"] - (1.5 * database[newid]["TrueSkillSigma"])) * 20

                if self.sbmm == True:
                    try:
                        mymmr += random.randint(0,100)
                    except:
                        print(f"Couldnt add random to mmr for some reason")
                else:
                    mymmr = random.randint(1,200)

                name = interaction.user.name
                self.userlist[newid] = {"Time": 0, "Name": name, "mmr": mymmr}
                await asyncio.sleep(1)
                if newid in self.userlist:
                    await interaction.response.edit_message(content=f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**) (SBMM: {self.sbmm})*<a:rgb:1319062935057727511>", view=NewQueueButtons(self.size, self.range, self.userlist, self.number, self.sbmm))
                    await interaction.followup.send(content="You joined queue", ephemeral=True)
                else:
                    await interaction.response.send_message(content="Error. Please try again", ephemeral=True)
                print(self.userlist)
                printguildname = str(interaction.guild.name)
                printedlist = [printguildname]
                for x in self.userlist:
                    name = self.userlist[x]["Name"]
                    mmr = self.userlist[x]["mmr"]
                    time = self.userlist[x]["Time"]
                    printedlist.append([name, x, mmr, time])
                # print(printedlist)

        while len(self.userlist) > 0:

            await asyncio.sleep(20)
            if newid in self.userlist:
                oldtime = self.userlist[newid]["Time"]
                self.userlist[newid]["Time"] += 30 # 20 seconds = 30 to time value
                newtime = self.userlist[newid]["Time"]
                if oldtime == newtime:
                    name = self.userlist[newid]["Name"]
                    print("Queue time error: ", name)

            if newid in self.userlist:
                if self.userlist[newid]["Time"] >= 800: # 800 = 13:20 i think
                    try:
                        print(f"Removed {newid} from queue for inactivity")
                        self.userlist.pop(newid, None)
                    except:  
                        print(f"Tried to remove {newid} from userlist but failed\nUserlist:\n{self.userlist}")

                    atstring = "<@" + str(newid) + "> You have been in queue for a while, so you were removed automatically. Feel free to rejoin."
                    await interaction.edit_original_response(content=f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**) (SBMM: {self.sbmm})*<a:rgb:1319062935057727511>", view=NewQueueButtons(self.size, self.range, self.userlist, self.number, self.sbmm))
                    await interaction.followup.send(content=atstring, ephemeral=True)

                    if len(self.userlist) == 0:
                        mychannel = interaction.channel
                        async for messages in mychannel.history(limit=50, oldest_first=False):
                            if messages.author == client.user:
                                if "Queue:" in messages.content:
                                    await messages.delete()
                                    break

                        # await interaction.channel.send(f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>", view=NewQueueButtons(self.size, self.range, self.userlist, self.number))
                        await interaction.channel.send(content=f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**) (SBMM: {self.sbmm})*<a:rgb:1319062935057727511>", view=NewQueueButtons(self.size, self.range, self.userlist, self.number, self.sbmm))
        

            printguildname = str(interaction.guild.name)
            printedlist = [printguildname]
            for x in self.userlist:
                name = self.userlist[x]["Name"]

                try:
                    mmr = self.userlist[x]["mmr"]
                except:
                    mmr = 1
                    print(f"JoinQueueButton, MMR error for user {name} {x}")

                time = self.userlist[x]["Time"]
                printedlist.append([name, x, mmr, time])
            # print(printedlist)

            if len(self.userlist) >= self.size:
                half = int(self.size / 2)
                closestdiff = 99999

                if half == 1:

                    mymmr = self.userlist[newid]["mmr"]

                    for x in self.userlist:
                        if x != newid:
                            try:
                                mmr = self.userlist[x]["mmr"]
                            except:
                                mmr = 2
                            difference = abs(mmr - mymmr) - (self.userlist[x]["Time"])
                            flatdifference = abs(mmr - mymmr)
                            if "LastOpponent" in database[newid]:
                                if database[newid]["LastOpponent"] == x:
                                    difference += 90

                            # print(f"MyID: {newid} - MyMMR: {mymmr}\noppID: {x} - oppMMR: {mmr}")
                            if difference < closestdiff:
                                closestdiff = difference
                                closestuser = x
                                finalflatdifference = flatdifference

                    finaldifference = closestdiff

                    group1 = [str(newid)]
                    group2 = [str(closestuser)]

                if half >= 2:
                    targetsum = 0
                    for x in self.userlist:
                        mmr = self.userlist[x]["mmr"]
                        targetsum += mmr

                    targetsum /= half

                    bestgroup = None
                    for group in combinations(self.userlist, half):
                        groupsum = 0
                        for x in group:
                            mmr = self.userlist[x]["mmr"]
                            groupsum += mmr

                        diff = abs(targetsum - groupsum)
                        if diff < closestdiff:
                            closestdiff = diff
                            bestgroup = group
                            bestmmr = groupsum

                    group1 = list(bestgroup)

                    otherusers = []
                    for x in self.userlist:
                        if x not in group1:
                            otherusers.append(x)

                    bestgroup = None
                    closestdiff = 99999
                    for group in combinations(otherusers, half):
                        groupsum = 0
                        for x in group:
                            mmr = self.userlist[x]["mmr"]
                            groupsum += mmr

                        diff = abs(bestmmr - groupsum)
                        if diff < closestdiff:
                            closestdiff = diff
                            bestgroup = group
                            secondmmr = groupsum

                    group2 = list(bestgroup)

                    finaldifference = abs(bestmmr - secondmmr)

                foundmatch = False

                if half == 1:
                    if finaldifference <= 0:
                        if isinstance(self.range, int):
                            if finalflatdifference < self.range:
                                foundmatch = True
                        if isinstance(self.range, str):
                            foundmatch = True

                if half >= 2:
                    if isinstance(self.range, int):
                        if finalflatdifference < self.range:
                            foundmatch = True
                    if isinstance(self.range, str):
                        foundmatch = True

                if foundmatch == True:
                    for x in group1:
                        self.userlist.pop(x, None)
                    for x in group2:
                        self.userlist.pop(x, None)

                    print1 = []
                    print2 = []
                    for x in group1:
                        target = await interaction.guild.fetch_member(int(x))
                        userid = target.id
                        ping = "<@" + str(userid) + ">"
                        print1.append(ping)
                    for x in group2:
                        target = await interaction.guild.fetch_member(int(x))
                        userid = target.id
                        ping = "<@" + str(userid) + ">"
                        print2.append(ping)

                    response = "empty"
                    blueteam = group1
                    redteam = group2
                    bluevotes = []
                    redvotes = []
                    cancelvotes = []
                    result=None
                    newstring = ""
                    # if "gamedata" in database:
                    #     if "gamename" in database["gamedata"]:
                    #         newstring = generatequeuetext(interaction, guildstring)
                    # else:
                    #     newstring = ""

                    newstring = await generatequeuetext(interaction, guildstring)

                    if len(group1) == 1:
                        blueuser = await interaction.guild.fetch_member(int(group1[0]))
                        bluename = blueuser.display_name
                    else:
                        bluename = "Blue Team"
                    if len(group2) == 1:
                        reduser = await interaction.guild.fetch_member(int(group2[0]))
                        redname = reduser.display_name
                    else:
                        redname = "Red Team"

                    if len(self.userlist) >= 0:
                        async for messages in interaction.channel.history(limit=50, oldest_first=False):
                            if messages.author == client.user:
                                if "Queue:" in messages.content:
                                    await messages.edit(content=f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>")
                                    break
                        
                    await interaction.channel.send(f"Match Found!\nPlease select the winning team\n🟦Blue Team: {print1}\n🟥Red Team: {print2}\n{newstring}", view=VoteButtons(bluevotes, redvotes, cancelvotes, blueteam, redteam, guildstring, undostring, result, bluename, redname))

                    if len(self.userlist) == 0:
                        mychannel = interaction.channel
                        async for messages in mychannel.history(limit=50, oldest_first=False):
                            if messages.author == client.user:
                                if "Queue:" in messages.content:
                                    await messages.delete()
                                    break

                        await interaction.channel.send(f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**) (SBMM: {self.sbmm})*<a:rgb:1319062935057727511>", view=NewQueueButtons(self.size, self.range, self.userlist, self.number, self.sbmm))
                        self.userlist.clear()


    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.red)
    async def NewLeaveQueueButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        user = interaction.user
        id = str(user.id)
        if id in self.userlist:
            del self.userlist[id]

        printguildname = str(interaction.guild.name)
        printedlist = [printguildname]
        for x in self.userlist:
            name = self.userlist[x]["Name"]
            mmr = self.userlist[x]["mmr"]
            time = self.userlist[x]["Time"]
            printedlist.append([name, x, mmr, time])

        await interaction.response.edit_message(content=f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**) (SBMM: {self.sbmm})*<a:rgb:1319062935057727511>")
        await interaction.followup.send(content="You left queue", ephemeral=True)
        print(printedlist)


    @discord.ui.button(label="Staff: Stop Queue", style=discord.ButtonStyle.gray)
    async def NewStopQueueButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        valid = False
        user = interaction.user        
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 1:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if valid == True:
            await interaction.response.edit_message(content="Queue stopped", view=None)
            self.userlist.clear()
            print(self.userlist)


class VoteButtons(discord.ui.View): # 1.1 uses embeds #
    def __init__(self, bluevotes, redvotes, cancelvotes, blueteam, redteam, guildstring, undostring, result, bluename, redname):
        super().__init__(timeout=None)
        self.bluevotes=bluevotes
        self.redvotes=redvotes
        self.cancelvotes=cancelvotes
        self.blueteam=blueteam
        self.redteam=redteam
        self.guildstring=guildstring
        self.undostring=undostring
        self.result=result
        self.bluename=bluename
        self.redname=redname

        # Set button labels to variables
        self.BlueButton.label = self.bluename
        self.RedButton.label = self.redname


    @discord.ui.button(label="bluename", style=discord.ButtonStyle.blurple)
    async def BlueButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.blueteam or str(interaction.user.id) in self.redteam:
            # if interaction.user.id not in self.bluevotes:
            self.bluevotes.append(str(interaction.user.id))
            await interaction.response.send_message(content="You selected Blue Team", ephemeral=True)
            if str(interaction.user.id) in self.redvotes:
                self.redvotes.remove(str(interaction.user.id))
            if str(interaction.user.id) in self.cancelvotes:
                self.cancelvotes.remove(str(interaction.user.id))
            self.bluevotes = list(set(self.bluevotes))

        redvotenames = []
        for x in self.redvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            redvotenames.append(name)
        bluevotenames = []
        for x in self.bluevotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            bluevotenames.append(name)
        cancelvotenames = []
        for x in self.cancelvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            cancelvotenames.append(name)
        print(f"\nRedvotes:{redvotenames}\nBluevotes:{bluevotenames}\nCancelvotes:{cancelvotenames}")

        if len(self.bluevotes) > len(self.redteam):
            if self.result == None:
                self.result = "BlueWin"
                embed = await rankcalc(interaction, self.blueteam, self.redteam, self.guildstring, self.undostring)
                # newstring = "Blue Team Wins!\n" + bigstring
                # await interaction.followup.send(content=newstring, view=None)
                # await interaction.followup.send(content=bigstring)
                await interaction.message.edit(content=None, embed=embed, view=None)

    @discord.ui.button(label="redname", style=discord.ButtonStyle.red)
    async def RedButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.blueteam or str(interaction.user.id) in self.redteam:
            # if interaction.user.id not in self.redvotes:
            self.redvotes.append(str(interaction.user.id))
            await interaction.response.send_message(content="You selected Red Team", ephemeral=True)
            if str(interaction.user.id) in self.bluevotes:
                self.bluevotes.remove(str(interaction.user.id))
            if str(interaction.user.id) in self.cancelvotes:
                self.cancelvotes.remove(str(interaction.user.id))
            self.redvotes = list(set(self.redvotes))

        redvotenames = []
        for x in self.redvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            redvotenames.append(name)
        bluevotenames = []
        for x in self.bluevotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            bluevotenames.append(name)
        cancelvotenames = []
        for x in self.cancelvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            cancelvotenames.append(name)
        print(f"\nRedvotes:{redvotenames}\nBluevotes:{bluevotenames}\nCancelvotes:{cancelvotenames}")

        if len(self.redvotes) > len(self.blueteam):
            if self.result == None:
                self.result = "RedWin"
                embed = await rankcalc(interaction, self.redteam, self.blueteam, self.guildstring, self.undostring)
                # newstring = "Red Team Wins!\n" + bigstring
                # await interaction.followup.send(content=newstring, view=None)
                # await interaction.followup.send(content=bigstring)
                await interaction.message.edit(content=None, embed=embed, view=None)

    @discord.ui.button(label="Cancel Match", style=discord.ButtonStyle.gray)
    async def CancelButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.blueteam or str(interaction.user.id) in self.redteam:
            # if interaction.user.id not in self.cancelvotes:
            self.cancelvotes.append(str(interaction.user.id))
            await interaction.response.send_message(content="You selected Cancel Match", ephemeral=True)
            if str(interaction.user.id) in self.bluevotes:
                self.bluevotes.remove(str(interaction.user.id))
            if str(interaction.user.id) in self.redvotes:
                self.redvotes.remove(str(interaction.user.id))
            self.cancelvotes = list(set(self.cancelvotes))

        redvotenames = []
        for x in self.redvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            redvotenames.append(name)
        bluevotenames = []
        for x in self.bluevotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            bluevotenames.append(name)
        cancelvotenames = []
        for x in self.cancelvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            cancelvotenames.append(name)
        print(f"\nRedvotes:{redvotenames}\nBluevotes:{bluevotenames}\nCancelvotes:{cancelvotenames}")

        if len(self.cancelvotes) > len(self.blueteam):
            if self.result == None:
                self.result = "Canceled"
                # await interaction.followup.send(content="Match canceled", view=None)
                await interaction.message.edit(content="Match canceled", view=None)
                # await interaction.followup.send(content="Match canceled")

    @discord.ui.button(label="Staff Override: Cancel", style=discord.ButtonStyle.gray)
    async def OverrideBButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        valid = False

        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in interaction.message.author.roles:
                    valid = True

        if interaction.user.guild_permissions.manage_guild == True or interaction.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
            valid = True

        if valid==True:
            if self.result == None:
                self.result = "Canceled"
                string = (f"Match canceled by {interaction.user.id}")
                await interaction.message.edit(content=string, view=None)


@client.tree.command(name="adjustuser", description="Adjust a user's details") # 0.1 #
@app_commands.describe(target = "The user to adjust")
@app_commands.describe(zsr = "ZSR, the default MMR")
@app_commands.describe(uncertainty = "ZSR Uncertainty")
@app_commands.describe(elo = "Elo")
@app_commands.describe(trueskillmu = "TrueSkill Mu")
@app_commands.describe(trueskillsigma = "TrueSkill Sigma")
@app_commands.describe(wins = "Total Wins")
@app_commands.describe(losses = "Total Losses")
@app_commands.describe(seasonwins = "Season Wins")
@app_commands.describe(seasonlosses = "Season Losses")
@app_commands.describe(streak = "Win Streak")
async def adjustuser(interaction: discord.Interaction, target: discord.Member, zsr: int = None, elo: int = None, trueskillmu: float = None, trueskillsigma: float = None, wins: int = None, losses: int = None, seasonwins: int = None, seasonlosses: int = None, streak: int = None, uncertainty: int = None):
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        user = interaction.user
        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 2:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

    if valid == True:
        message = ""
        id = str(target.id)

        if id not in database:
            database[id] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
        
        if zsr is not None:
            if zsr >= 0:
                database[id]["mmr"] = zsr
                message += f"ZSR adjusted to {zsr}\n"

        if uncertainty is not None:
            if 1000 >= uncertainty >= 0:
                database[id]["uncertainty"] = uncertainty
                message += f"Uncertainty adjusted to {uncertainty}\n"

        if elo is not None:
            if elo >= 0:
                database[id]["Elo"] = elo
                message += f"Elo adjusted to {elo}\n"

        if trueskillmu is not None:
            if trueskillmu >= 0:
                database[id]["TrueSkillMu"] = trueskillmu
                message += f"TrueSkill Mu adjusted to {trueskillmu}\n"

        if trueskillsigma is not None:
            if trueskillsigma >= 0:
                database[id]["TrueSkillSigma"] = trueskillsigma
                message += f"TrueSkill Sigma adjusted to {trueskillsigma}\n"

        if wins is not None:
            if wins >= 0:
                database[id]["wins"] = wins
                message += f"Total wins adjusted to {wins}\n"

        if losses is not None:
            if losses >= 0:
                database[id]["losses"] = losses
                message += f"Total losses adjusted to {losses}\n"

        if seasonwins is not None:
            if seasonwins >= 0:
                database[id]["seasonwins"] = seasonwins
                message += f"Season wins adjusted to {seasonwins}\n"

        if seasonlosses is not None:
            if seasonlosses >= 0:
                database[id]["seasonlosses"] = seasonlosses
                message += f"Season losses adjusted to {seasonlosses}\n"

        if streak is not None:
            if streak >= 0:
                database[id]["streak"] = streak
                message += f"Win streak adjusted to {streak}\n"

        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)

        await interaction.response.send_message(message)

    else:
        await interaction.response.send_message("You do not have permission!", ephemeral=True)


@client.tree.command(name="rankban", description="Ban a user from ranked") # Slash command 0.1
@app_commands.describe(targetuser = "Which user do you want to ban from ranked?")
async def rankban(interaction: discord.Interaction, targetuser: discord.User):
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    user = interaction.user
    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if valid == True:
        bigstring = ""

        y = str(targetuser.id)
        name = targetuser.global_name

        if y not in database:
            database[y] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
            bigstring = f"{name} was not registered and has been added to the database.\n"

        database[y]["RankBan"] = "True"
        bigstring = bigstring + f"{name} has been banned from ranked."

    await interaction.response.send_message(bigstring)

    with open(guildstring, "w") as outfile:
        json.dump(database, outfile, indent = 4)


@client.tree.command(name="rankunban", description="Unban a user from ranked") # Slash command 0.1
@app_commands.describe(targetuser = "Which user do you want to unban from ranked?")
async def rankunban(interaction: discord.Interaction, targetuser: discord.User):
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    user = interaction.user
    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if valid == True:
        bigstring = ""

        y = str(targetuser.id)
        name = targetuser.global_name

        if y not in database:
            database[y] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
            bigstring = f"{name} was not registered and has been added to the database.\n"

        database[y]["RankBan"] = "False"
        bigstring = bigstring + f"{name} has been unbanned from ranked."

        await interaction.response.send_message(bigstring)

    with open(guildstring, "w") as outfile:
        json.dump(database, outfile, indent = 4)


@client.tree.command(name="status", description="Set the bot's Status", guild=guildid) # Slash command 0.1
@app_commands.describe(status = "status")
async def status(interaction: discord.Interaction, status: str):
    if str(interaction.user.id) == "215277233638604800":
        if status == "None":
            await client.change_presence(activity=None)
        if status == "Streaming":
            await client.change_presence(activity=discord.Streaming(name="Watching Zing on Twitch", url='https://www.twitch.tv/coachzing'))
        else:
            await client.change_presence(activity=discord.CustomActivity(name=status))

        await interaction.response.send_message("Status updated")


@client.tree.command(name="backup", description="create a backup of your server's database") # Slash command 0.1
async def backup(interaction: discord.Interaction):
    if interaction.guild:
        user = interaction.user
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)
        valid = False
        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True
        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 2:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

        if valid == True:
            await interaction.response.send_message("Data backup:", file=discord.File(guildstring))


@client.tree.command(name="refreshroles", description="Refresh your server's ranked roles") # proper check for role permissions
async def refreshroles(interaction: discord.Interaction):
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        user = interaction.user
        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 2:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

        guild = interaction.guild
        botuser = interaction.guild.me
        permissions1 = botuser.guild_permissions.manage_roles
        mastername = database["rankroles"]["master"]
        masterrole = discord.utils.get(guild.roles, name=mastername)
        bothasrolepermissions = False
        for x in botuser.roles:
            if x > masterrole:
                if permissions1:
                    bothasrolepermissions = True
                    
        if bothasrolepermissions == False:
            valid = False
        
        if valid == True:
            await interaction.response.send_message(f"This command is laggy. Please do not run this command often\nThis may take a moment...")

            if "gamedata" not in database:
                database["gamedata"] = {}
            if "mastertier" in database["gamedata"]:
                tier2 = database["gamedata"]["silvertier"]
                tier3 = database["gamedata"]["goldtier"]
                tier4 = database["gamedata"]["platinumtier"]
                tier5 = database["gamedata"]["diamondtier"]
                tier6 = database["gamedata"]["mastertier"]
            else:
                tier2 = 200
                tier3 = 400
                tier4 = 600
                tier5 = 800
                tier6 = 1000

            if "rankroles" in database:
                print("rankroles in database")
                guild = interaction.guild
                bronzename = database["rankroles"]["bronze"]
                bronzerole = discord.utils.get(guild.roles, name=bronzename)
                silvername = database["rankroles"]["silver"]
                silverrole = discord.utils.get(guild.roles, name=silvername)
                goldname = database["rankroles"]["gold"]
                goldrole = discord.utils.get(guild.roles, name=goldname)
                platname = database["rankroles"]["platinum"]
                platrole = discord.utils.get(guild.roles, name=platname)
                diamondname = database["rankroles"]["diamond"]
                diamondrole = discord.utils.get(guild.roles, name=diamondname)
                mastername = database["rankroles"]["master"]
                masterrole = discord.utils.get(guild.roles, name=mastername)

            count = 0
            for members in database:
                if "mmr" in database[members]:
                    count += 1
                    mmr = database[members]["mmr"]
                    newtier = 1
                    if mmr >= tier2:
                        newtier = 2
                    if mmr >= tier3:
                        newtier = 3
                    if mmr >= tier4:
                        newtier = 4
                    if mmr >= tier5:
                        newtier = 5
                    if mmr >= tier6:
                        newtier = 6

                    try:
                        user = await interaction.guild.fetch_member(int(members))

                        if newtier != 1:
                            if bronzerole in user.roles:
                                await user.remove_roles(bronzerole)
                        if newtier != 2:
                            if silverrole in user.roles:
                                await user.remove_roles(silverrole)
                        if newtier != 3:
                            if goldrole in user.roles:
                                await user.remove_roles(goldrole)
                        if newtier != 4:
                            if platrole in user.roles:
                                await user.remove_roles(platrole)
                        if newtier != 5:
                            if diamondrole in user.roles:
                                await user.remove_roles(diamondrole)
                        if newtier != 6:
                            if masterrole in user.roles:
                                await user.remove_roles(masterrole)

                        if newtier == 1:
                            if bronzerole not in user.roles:
                                await user.add_roles(bronzerole)
                        if newtier == 2:
                            if silverrole not in user.roles:
                                await user.add_roles(silverrole)
                        if newtier == 3:
                            if goldrole not in user.roles:
                                await user.add_roles(goldrole)
                        if newtier == 4:
                            if platrole not in user.roles:
                                await user.add_roles(platrole)
                        if newtier == 5:
                            if diamondrole not in user.roles:
                                await user.add_roles(diamondrole)
                        if newtier == 6:
                            if masterrole not in user.roles:
                                await user.add_roles(masterrole)  

                    except:
                        print(f"User not found in server: {members}")

            await interaction.channel.send(f"Updated {count} user's roles")


@client.tree.command(name="randomtext", description="Generate random text like from the queue") # 0.1 #
async def randomtext(interaction: discord.Interaction):
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if "queuetext" in database:
        newstring = await generatequeuetext(interaction, guildstring)
        await interaction.response.send_message(newstring)
    else:
        await interaction.response.send_message("No queue text found. Configure with /configqueuetext")


###############################


async def placecalc(context, results, guildstring):
    undostring = str(guildstring) + "undo.json"
    guildstring = str(guildstring) + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if not os.path.exists(undostring):
        undodatabase = {}
        with open(undostring, 'w') as file:
            json.dump(undodatabase, file, indent=4)

    with open(undostring, 'r') as openfile:
        undodatabase = json.load(openfile)

    for x in results:
        try:
            if x in database:
                undodatabase[x] = database[x]
        except:
            # print("Error, user not added to undo database")
            pass

    with open(undostring, "w") as outfile:
        json.dump(undodatabase, outfile, indent=4)

    serveraveragemmr = 0
    totalmmr = 0
    totalusers = 0
    numberofplayers = 0

    emoji_1, emoji_2, emoji_3, emoji_4, emoji_5, emoji_6 = loademoji(guildstring)

    if "gamedata" not in database:
        database["gamedata"] = {}
    if "mastertier" in database["gamedata"]:
        tier2 = database["gamedata"]["silvertier"]
        tier3 = database["gamedata"]["goldtier"]
        tier4 = database["gamedata"]["platinumtier"]
        tier5 = database["gamedata"]["diamondtier"]
        tier6 = database["gamedata"]["mastertier"]
    else:
        tier2 = 200
        tier3 = 400
        tier4 = 600
        tier5 = 800
        tier6 = 1000

    if "gamedata" not in database:
        database["gamedata"] = {}
    if "rankbase" in database["gamedata"]:
        rankbase = database["gamedata"]["rankbase"]
    else:
        rankbase = 30

    sorteddb = dict(
        sorted(
            ((k, v) for k, v in database.items() if "mmr" in v),
            key=lambda item: item[1]["mmr"],
            reverse=True))

    for x in sorteddb:
        if database[x]["uncertainty"] < 500:
            totalmmr += database[x]["mmr"]
            totalusers += 1

    if totalusers > 0:
        serveraveragemmr = totalmmr / totalusers
    if totalusers == 0:
        serveraveragemmr = 0

    for x in results:
        results[x]["ZSR"] = database[x]["mmr"]
        results[x]["Elo"] = database[x]["Elo"]
        results[x]["ZSRChange"] = 0
        results[x]["EloChange"] = 0
        numberofplayers += 1

    for x in results:
        for y in results:
            if x != y:
                if results[x]["Placement"] < results[y]["Placement"]:
                    winner = x
                    loser = y

                    winnerzsr = database[winner]["mmr"]
                    loserzsr = database[loser]["mmr"]
                    winnerunc = database[winner]["uncertainty"]
                    loserunc = database[loser]["uncertainty"]
                    winnerelo = database[winner]["Elo"]
                    loserelo = database[loser]["Elo"]

                    winneradjustedmmr = max((((winnerzsr * (1000 - winnerunc) / 1000) + (serveraveragemmr * winnerunc / 1000)) / 2), winnerzsr)
                    loseradjustedmmr = max((((loserzsr * (1000 - loserunc) / 1000) + (serveraveragemmr * loserunc / 1000)) / 2), loserzsr)

                    results[winner]["ZSRChange"] += rankbase * (2 / numberofplayers) * (1 - (1 / (1 + (rankscaling ** (loseradjustedmmr - winnerzsr)))))
                    results[loser]["ZSRChange"] -= rankbase * (2 / numberofplayers) * (1 - (1 / (1 + (rankscaling ** (loserzsr - winneradjustedmmr)))))

                    winnergain, loserloss = elo_rating(winnerelo, loserelo, rankbase)
                    results[winner]["EloChange"] += winnergain
                    results[loser]["EloChange"] -= loserloss

                    for z in [winner, loser]:
                        if loserzsr >= winnerzsr + 100:
                            database[z]["uncertainty"] += 50
                        else:
                            database[z]["uncertainty"] -= 50

                    print(f"Winner: {results[winner]} / {results[winner]["ZSRChange"]}\nLoser: {results[loser]} / {results[winner]["ZSRChange"]}")

    print(results)

    bigstring = "Results:\n"
    leftstring = ""
    rightstring = ""

    for x in results:
        database[x]["mmr"] = round(database[x]["mmr"])
        database[x]["Elo"] = round(database[x]["Elo"])
        results[x]["ZSRChange"] = round(results[x]["ZSRChange"])
        results[x]["EloChange"] = round(results[x]["EloChange"])

        newmmr = database[x]["mmr"] + results[x]["ZSRChange"]

        emoji = emoji_1
        if newmmr >= tier2:
            emoji = emoji_2
        if newmmr >= tier3:
            emoji = emoji_3
        if newmmr >= tier4:
            emoji = emoji_4
        if newmmr >= tier5:
            emoji = emoji_5
        if newmmr >= tier6:
            emoji = emoji_6

        tempstring = f"**{results[x]["Placement"]}:** {results[x]["Name"]} - {database[x]["mmr"]} -> {emoji}{newmmr}{emoji}\n"
        leftstring += f"**{results[x]["Placement"]}:** {results[x]["Name"]}\n"
        rightstring += f"{database[x]["mmr"]} -> {emoji}{newmmr}{emoji}\n"
        bigstring = bigstring + tempstring

        database[x]["mmr"] += results[x]["ZSRChange"]
        database[x]["Elo"] += results[x]["EloChange"]
        database[x]["mmr"] = round(database[x]["mmr"])
        database[x]["Elo"] = round(database[x]["Elo"])

        if database[x]["mmr"] < 0:
            database[x]["mmr"] = 0
        if database[x]["Elo"] < 0:
            database[x]["Elo"] = 0

    print(bigstring)

    embed = discord.Embed(
        title = "Results:"
    )
    embed.add_field(name="", value=leftstring, inline=True)
    embed.add_field(name="", value=rightstring, inline=True)

    with open(guildstring, "w") as outfile:
        json.dump(database, outfile, indent = 4)

    return embed


@client.tree.command(name="placement", description="Submit a game with many users having specific placings. WIP", guild=guildid) # 1.0 #
async def placement(interaction: discord.Interaction):
    user = interaction.user
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)
    
    if "serverroles" not in database:
        database["serverroles"] = {}

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    for x in database["serverroles"]:
        if database["serverroles"][x] >= 1:
            myrole = discord.utils.get(interaction.guild.roles, name=x)
            if myrole in user.roles:
                valid = True


    if valid == True:
        looping = True
        dummy = PlacementSubmitButtons()
        
        await interaction.response.send_message("Input Users/Placings", view=dummy)


class PlacementSubmitButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.userdict={}
        self.tempusers = []
        self.tempplacing = 1

    @discord.ui.button(label="Add Selection", style=discord.ButtonStyle.blurple)
    async def PlacementSubmitUsersButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.tempusers) > 0:
            for x in self.tempusers:
                if str(x.id) not in self.userdict:
                    userid = str(x.id)
                    username = x.name
                    self.userdict[userid] = {}
                    self.userdict[userid]["Placement"] = self.tempplacing
                    self.userdict[userid]["Name"] = username

            self.tempplacing += 1
            self.tempusers = []

            print(self.userdict)
            printstring = ""
            for x in self.userdict:
                printstring += f"{self.userdict[x]["Placement"], self.userdict[x]["Name"]}\n"

            await interaction.response.edit_message(content=printstring)

    @discord.ui.select(max_values=25, min_values=1, cls=discord.ui.UserSelect)
    async def PlacementAddUsers(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.tempusers = select.values
        await interaction.response.defer(ephemeral=True)
    

    @discord.ui.button(label="Submit Final Results", style=discord.ButtonStyle.green)
    async def PlacementDoneButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await placecalc(interaction, self.userdict, interaction.guild.id)
        await interaction.channel.send(embed=embed)   


    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def PlacementCancelButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Canceled submission", view=None)
        return


def assign_roles(users, userlist):
    POSITIONS = ["Top", "Jg", "Mid", "Bot", "Sup"]

    names = list(users)

    for tempteam in permutations(names):
        assignment = []
        for role, user in zip(POSITIONS, tempteam):
            if role in userlist[user]["Roles"]:
                assignment.append((user, role))
            else:
                print(f"Assignment\n{assignment}\n")
                break
        else:
            return assignment
        
    return None


def find_best_teams(userlist):
    allteams = []

    for team1users in combinations(userlist, 5):
        team2temp = [u for u in userlist if u not in team1users]
        for team2users in combinations(team2temp, 5):
            team1mmr = 0
            team2mmr = 0
            for x in team1users:
                team1mmr += userlist[x]["mmr"]
            for x in team2users:
                team2mmr += userlist[x]["mmr"]
            difference = abs(team1mmr - team2mmr)

            allteams.append({
                "team1": list(team1users),
                "team2": list(team2users),
                "team1_mmr": team1mmr,
                "team2_mmr": team2mmr,
                "mmr_diff": difference
            })
                
            allteamssorted = sorted(allteams, key=lambda d: d['mmr_diff'], reverse=True)

            for x in range(len(allteamssorted)):
                newteam1users = allteamssorted[x]["team1"]
                newteam2users = allteamssorted[x]["team2"]

                if not assign_roles(newteam1users, userlist):
                    continue

                if not assign_roles(newteam2users, userlist):
                    continue
                    
                team1roles = assign_roles(newteam1users, userlist)
                team2roles = assign_roles(newteam2users, userlist)

                if team1roles == False or team2roles == False:
                    continue

                print(team1roles)
                print(team2roles)
                return team1roles, team2roles


@client.tree.command(name="lolqueue", description="Start a League of Legends matchmaking queue", guild=guildid) # 0.1
async def lolqueue(interaction: discord.Interaction):
    user = interaction.user
    range = "None"
    valid = False
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if valid == True:
        userlist = {}
        await interaction.response.send_message(f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(userlist)}**)*<a:rgb:1319062935057727511>", view=LeagueQueueButtons(range, userlist))


class LeagueQueueButtons(discord.ui.View): # 3.1 Added some randomness to MM
    def __init__(self, range, userlist):
        super().__init__(timeout=None)
        self.range = range
        self.userlist = userlist

    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.green)
    async def NewJoinQueueButton(self, interaction: discord.Interaction, button: discord.ui.Button):

        # queuebutton = interaction.message
        # mymessage = await interaction.channel.fetch_message(queuebutton.id)

        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        undostring = str(interaction.guild.id) + "undo" + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        newuser = interaction.user
        newid = str(newuser.id)

        if newid not in database:
            # database[newid] = {"mmr": 0, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 1000}
            await interaction.response.send_message(content="You have to register first!", ephemeral=True)

        if newid in database:
            # if "Elo" not in database[newid]:
            #     database[newid]["Elo"] = findstartingelo(guildstring)
            if "TrueSkillMu" not in database[newid]:
                database[newid]["TrueSkillMu"] = 25
            if "TrueSkillSigma" not in database[newid]:
                database[newid]["TrueSkillSigma"] = 8.333
            if "streak" not in database[newid]:
                database[newid]["streak"] = 0
            if "uncertainty" not in database[newid]:
                database[newid]["uncertainty"] = 1000

        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)

        if "RankBan" in database[newid]:
            if database[newid]["RankBan"] == "True":
                await interaction.response.send_message(content="You are banned from queue and cannot join", ephemeral=True)

        if "RankBan" not in database[newid] or database[newid]["RankBan"] == "False":
            if newid not in self.userlist:
                
                mymmr = database[newid]["mmr"] + (database[newid]["uncertainty"] / 10)
                if "gamedata" in database:
                    if "mmrtype" in database["gamedata"]:
                        if database["gamedata"]["mmrtype"].lower() == "elo":
                            mymmr = database[newid]["Elo"]
                        elif database["gamedata"]["mmrtype"].lower() == "trueskill":
                            mymmr = (database[newid]["TrueSkillMu"] - (1.5 * database[newid]["TrueSkillSigma"])) * 25

                try:
                    mymmr += random.randint(0,100)
                except:
                    print(f"Couldnt add random to mmr for some reason")

                myroles = []
                TopRole = discord.utils.get(interaction.guild.roles, name="Top")
                MidRole = discord.utils.get(interaction.guild.roles, name="Mid")
                JgRole = discord.utils.get(interaction.guild.roles, name="Jungle")
                BotRole = discord.utils.get(interaction.guild.roles, name="Bot")
                SupRole = discord.utils.get(interaction.guild.roles, name="Support")
                if TopRole in interaction.user.roles:
                    myroles.append("Top")
                    mymmr -= 30
                if MidRole in interaction.user.roles:
                    myroles.append("Mid")
                    mymmr -= 30
                if JgRole in interaction.user.roles:
                    myroles.append("Jg")
                    mymmr -= 30
                if BotRole in interaction.user.roles:
                    myroles.append("Bot")
                    mymmr -= 30
                if SupRole in interaction.user.roles:
                    myroles.append("Sup")
                    mymmr -= 30

                if len(myroles) == 0:
                    await interaction.response.send_message(content="You must have at least one role", ephemeral=True)
                    return

                name = interaction.user.name
                self.userlist[newid] = {"Time": 0, "Name": name, "mmr": mymmr, "Roles": myroles}
                await asyncio.sleep(1)
                if newid in self.userlist:
                    await interaction.response.edit_message(content=f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>", view=LeagueQueueButtons(self.range, self.userlist))
                    await interaction.followup.send(content="You joined queue", ephemeral=True)
                else:
                    await interaction.response.send_message(content="Error. Please try again", ephemeral=True)
                # print(self.userlist)
                # printguildname = str(interaction.guild.name)
                # printedlist = [printguildname]
                # for x in self.userlist:
                #     name = self.userlist[x]["Name"]
                #     mmr = self.userlist[x]["mmr"]
                #     time = self.userlist[x]["Time"]
                #     roles = self.userlist[x]["Roles"]
                #     printedlist.append([name, x, mmr, time, roles])
                # print(printedlist)

        while len(self.userlist) > 0:

            await asyncio.sleep(20)
            if newid in self.userlist:
                oldtime = self.userlist[newid]["Time"]
                self.userlist[newid]["Time"] += 20 # 20 seconds = 20 to time value
                newtime = self.userlist[newid]["Time"]
                if oldtime == newtime:
                    name = self.userlist[newid]["Name"]
                    print("Queue time error: ", name)

            if newid in self.userlist:
                if self.userlist[newid]["Time"] >= 800: # 800 = 13:20 i think
                    try:
                        print(f"Removed {newid} from queue for inactivity")
                        self.userlist.pop(newid, None)
                    except:  
                        print(f"Tried to remove {newid} from userlist but failed\nUserlist:\n{self.userlist}")

                    atstring = "<@" + str(newid) + "> You have been in queue for a while, so you were removed automatically. Feel free to rejoin."
                    await interaction.edit_original_response(content=f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>", view=LeagueQueueButtons(self.range, self.userlist))
                    await interaction.followup.send(content=atstring, ephemeral=True)

                    if len(self.userlist) == 0:
                        mychannel = interaction.channel
                        async for messages in mychannel.history(limit=150, oldest_first=False):
                            if messages.author == client.user:
                                if "Queue:" in messages.content:
                                    await messages.delete()
                                    break

                        # await interaction.channel.send(f"<a:rgb:1319062935057727511>**Queue:** *(size: {self.size})* *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>", view=NewQueueButtons(self.size, self.range, self.userlist, self.number))
                        await interaction.channel.send(content=f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>", view=LeagueQueueButtons(self.range, self.userlist))

            # printguildname = str(interaction.guild.name)
            # printedlist = [printguildname]
            # for x in self.userlist:
            #     name = self.userlist[x]["Name"]

            #     try:
            #         mmr = self.userlist[x]["mmr"]
            #     except:
            #         mmr = 1
            #         print(f"JoinQueueButton, MMR error for user {name} {x}")

            #     time = self.userlist[x]["Time"]
            #     printedlist.append([name, x, mmr, time])
            # print(printedlist)

            if len(self.userlist) >= 10:
                half = 5

                group1, group2 = find_best_teams(self.userlist)
                print(group1)
                print(group2)

                print(self.userlist)
                if group1 and group2:
                    for x in group1:
                        print(x)
                        self.userlist.pop(x[0])
                    for x in group2:
                        print(x)
                        self.userlist.pop(x[0])
                    print(self.userlist)

                    print1 = []
                    print2 = []
                    for x in group1:
                        mytempid = x[0] # ?
                        target = await interaction.guild.fetch_member(int(mytempid))
                        userid = target.id
                        ping = "<@" + str(userid) + ">"
                        print1.append(ping)
                    for x in group2:
                        mytempid = x[0] # ?
                        target = await interaction.guild.fetch_member(int(mytempid))
                        userid = target.id
                        ping = "<@" + str(userid) + ">"
                        print2.append(ping)

                    response = "empty"
                    blueteam = group1
                    redteam = group2
                    bluevotes = []
                    redvotes = []
                    cancelvotes = []
                    result=None
                    newstring = ""
                    # if "gamedata" in database:
                    #     if "gamename" in database["gamedata"]:
                    #         newstring = generatequeuetext(database["gamedata"]["gamename"])
                    # else:
                    #     newstring = ""

                    if len(group1) == 1:
                        blueuser = await interaction.guild.fetch_member(int(group1[0]))
                        bluename = blueuser.display_name
                    else:
                        bluename = "Blue Team"
                    if len(group2) == 1:
                        reduser = await interaction.guild.fetch_member(int(group2[0]))
                        redname = reduser.display_name
                    else:
                        redname = "Red Team"

                    if len(self.userlist) >= 0:
                        async for messages in interaction.channel.history(limit=50, oldest_first=False):
                            if messages.author == client.user:
                                if "Queue:" in messages.content:
                                    await messages.edit(content=f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>")
                                    break
                        

                    blueteamopgg = "https://op.gg/lol/multisearch/na?summoners="
                    redteamopgg = "https://op.gg/lol/multisearch/na?summoners="

                    try:
                        for x in group1:
                            account = database[x]["account"].split("#")
                            name = account[0]
                            tag = account[1]
                            blueteamopgg += (f"{name}%23{tag}%2C")

                        for x in group2:
                            account = database[x]["account"].split("#")
                            name = account[0]
                            tag = account[1]
                            redteamopgg += (f"{name}%23{tag}%2C")

                        blueteamopgg = blueteamopgg[:-3]
                        redteamopgg = redteamopgg[:-3]
                    except:
                        print("Error building multiopgg")
                    
                    await interaction.channel.send(f"Match Found!\nPlease select the winning team\nRoles in order:  Top  /  Jg  /  Mid  /  Bot  /  Sup\n🟦Blue Team: {print1}\n🟥Red Team: {print2}\nBlue team: {blueteamopgg}\nRed Team: {redteamopgg}", view=LeagueVoteButtons(bluevotes, redvotes, cancelvotes, blueteam, redteam, guildstring, undostring, result, bluename, redname))

                    if len(self.userlist) == 0:
                        mychannel = interaction.channel
                        async for messages in mychannel.history(limit=50, oldest_first=False):
                            if messages.author == client.user:
                                if "Queue:" in messages.content:
                                    await messages.delete()
                                    break

                        await interaction.channel.send(f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>", view=LeagueQueueButtons(self.range, self.userlist))
                        self.userlist.clear()


    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.red)
    async def NewLeaveQueueButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        user = interaction.user
        id = str(user.id)
        if id in self.userlist:
            del self.userlist[id]

        printguildname = str(interaction.guild.name)
        printedlist = [printguildname]
        for x in self.userlist:
            name = self.userlist[x]["Name"]
            mmr = self.userlist[x]["mmr"]
            time = self.userlist[x]["Time"]
            printedlist.append([name, x, mmr, time])

        await interaction.response.edit_message(content=f"<a:rgb:1319062935057727511>**Queue:** *(Members in queue: **{len(self.userlist)}**)*<a:rgb:1319062935057727511>")
        await interaction.followup.send(content="You left queue", ephemeral=True)
        print(printedlist)


    @discord.ui.button(label="Staff: Stop Queue", style=discord.ButtonStyle.gray)
    async def NewStopQueueButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        valid = False
        user = interaction.user        
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 1:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if valid == True:
            await interaction.response.edit_message(content="Queue stopped", view=None)
            self.userlist.clear()
            print(self.userlist)


class LeagueVoteButtons(discord.ui.View): # 1.1 uses embeds #
    def __init__(self, bluevotes, redvotes, cancelvotes, blueteam, redteam, guildstring, undostring, result, bluename, redname):
        super().__init__(timeout=None)
        self.bluevotes=bluevotes
        self.redvotes=redvotes
        self.cancelvotes=cancelvotes
        self.blueteam=blueteam
        self.redteam=redteam
        self.guildstring=guildstring
        self.undostring=undostring
        self.result=result
        self.bluename=bluename
        self.redname=redname

        # Set button labels to variables
        self.BlueButton.label = self.bluename
        self.RedButton.label = self.redname


    @discord.ui.button(label="bluename", style=discord.ButtonStyle.blurple)
    async def BlueButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.blueteam or str(interaction.user.id) in self.redteam:
            # if interaction.user.id not in self.bluevotes:
            self.bluevotes.append(str(interaction.user.id))
            await interaction.response.send_message(content="You selected Blue Team", ephemeral=True)
            if str(interaction.user.id) in self.redvotes:
                self.redvotes.remove(str(interaction.user.id))
            if str(interaction.user.id) in self.cancelvotes:
                self.cancelvotes.remove(str(interaction.user.id))
            self.bluevotes = list(set(self.bluevotes))

        redvotenames = []
        for x in self.redvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            redvotenames.append(name)
        bluevotenames = []
        for x in self.bluevotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            bluevotenames.append(name)
        cancelvotenames = []
        for x in self.cancelvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            cancelvotenames.append(name)
        print(f"\nRedvotes:{redvotenames}\nBluevotes:{bluevotenames}\nCancelvotes:{cancelvotenames}")

        if len(self.bluevotes) > len(self.redteam):
            if self.result == None:
                self.result = "BlueWin"
                embed = await rankcalc(interaction, self.blueteam, self.redteam, self.guildstring, self.undostring)
                # newstring = "Blue Team Wins!\n" + bigstring
                # await interaction.followup.send(content=newstring, view=None)
                # await interaction.followup.send(content=bigstring)
                await interaction.message.edit(content=None, embed=embed, view=None)

    @discord.ui.button(label="redname", style=discord.ButtonStyle.red)
    async def RedButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.blueteam or str(interaction.user.id) in self.redteam:
            # if interaction.user.id not in self.redvotes:
            self.redvotes.append(str(interaction.user.id))
            await interaction.response.send_message(content="You selected Red Team", ephemeral=True)
            if str(interaction.user.id) in self.bluevotes:
                self.bluevotes.remove(str(interaction.user.id))
            if str(interaction.user.id) in self.cancelvotes:
                self.cancelvotes.remove(str(interaction.user.id))
            self.redvotes = list(set(self.redvotes))

        redvotenames = []
        for x in self.redvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            redvotenames.append(name)
        bluevotenames = []
        for x in self.bluevotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            bluevotenames.append(name)
        cancelvotenames = []
        for x in self.cancelvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            cancelvotenames.append(name)
        print(f"\nRedvotes:{redvotenames}\nBluevotes:{bluevotenames}\nCancelvotes:{cancelvotenames}")

        if len(self.redvotes) > len(self.blueteam):
            if self.result == None:
                self.result = "RedWin"
                embed = await rankcalc(interaction, self.redteam, self.blueteam, self.guildstring, self.undostring)
                # newstring = "Red Team Wins!\n" + bigstring
                # await interaction.followup.send(content=newstring, view=None)
                # await interaction.followup.send(content=bigstring)
                await interaction.message.edit(content=None, embed=embed, view=None)

    @discord.ui.button(label="Cancel Match", style=discord.ButtonStyle.gray)
    async def CancelButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in self.blueteam or str(interaction.user.id) in self.redteam:
            # if interaction.user.id not in self.cancelvotes:
            self.cancelvotes.append(str(interaction.user.id))
            await interaction.response.send_message(content="You selected Cancel Match", ephemeral=True)
            if str(interaction.user.id) in self.bluevotes:
                self.bluevotes.remove(str(interaction.user.id))
            if str(interaction.user.id) in self.redvotes:
                self.redvotes.remove(str(interaction.user.id))
            self.cancelvotes = list(set(self.cancelvotes))

        redvotenames = []
        for x in self.redvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            redvotenames.append(name)
        bluevotenames = []
        for x in self.bluevotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            bluevotenames.append(name)
        cancelvotenames = []
        for x in self.cancelvotes:
            target = await interaction.guild.fetch_member(int(x))
            name = target.name
            cancelvotenames.append(name)
        print(f"\nRedvotes:{redvotenames}\nBluevotes:{bluevotenames}\nCancelvotes:{cancelvotenames}")

        if len(self.cancelvotes) > len(self.blueteam):
            if self.result == None:
                self.result = "Canceled"
                # await interaction.followup.send(content="Match canceled", view=None)
                await interaction.message.edit(content="Match canceled", view=None)
                # await interaction.followup.send(content="Match canceled")

    @discord.ui.button(label="Staff Override: Cancel", style=discord.ButtonStyle.gray)
    async def OverrideBButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        valid = False

        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in interaction.message.author.roles:
                    valid = True

        if interaction.user.guild_permissions.manage_guild == True or interaction.user.guild_permissions.administrator == True or str(interaction.user.id) == "215277233638604800":
            valid = True

        if valid==True:
            if self.result == None:
                self.result = "Canceled"
                string = (f"Match canceled by {interaction.user.id}")
                await interaction.message.edit(content=string, view=None)


@client.tree.command(name="leagueregister", description="Register a User for customs in league", guild=guildid) # 1.1 uses embeds #
@app_commands.describe(targetuser = "Which user is being registered?")
@app_commands.describe(usermmr = "What is the users ZSR/MMR?")
@app_commands.describe(accountname = "What is the users Account name and tag")
async def leagueregister(interaction: discord.Interaction, targetuser: discord.User, usermmr: int, accountname: str):
    # Iron 400
    # Bronze 500
    # Silver 600
    # Gold 700
    # Plat 800
    # Emerald 900
    # Diamond 1000
    # Master 1100
    # GM 1200
    # Chal 1300
    valid = False
    if interaction.guild:
        guildname = str(interaction.guild.id)
        guildstring = guildname + ".json"
        with open(guildstring, 'r') as openfile:
            database = json.load(openfile)

        user = interaction.user
        if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
            valid = True

        if "serverroles" in database:
            for x in database["serverroles"]:
                if database["serverroles"][x] >= 1:
                    myrole = discord.utils.get(interaction.guild.roles, name=x)
                    if myrole in user.roles:
                        valid = True

    if valid == True:
        # if targetuser.id not in database:
        database[x] = {"mmr": usermmr, "wins": 0, "losses": 0, "streak": 0, "uncertainty": 0, "Elo": findstartingelo(guildstring), "TrueSkillMu": 25, "TrueSkillSigma": 8.333, "account": accountname}
        with open(guildstring, "w") as outfile:
            json.dump(database, outfile, indent = 4)
        await interaction.response.send_message(f"User {targetuser.name} {accountname} added to database with {usermmr} MMR")


@client.tree.command(name="setaccountname", description="Set a user's account name", guild=guildid) # Slash command 0.1
@app_commands.describe(targetuser = "Which user do you want to change?")
@app_commands.describe(accountname = "What is the users Account name and tag")
async def setaccountname(interaction: discord.Interaction, targetuser: discord.User, accountname: str):
    user = interaction.user
    guildname = str(interaction.guild.id)
    guildstring = guildname + ".json"
    with open(guildstring, 'r') as openfile:
        database = json.load(openfile)

    if "serverroles" in database:
        for x in database["serverroles"]:
            if database["serverroles"][x] >= 1:
                myrole = discord.utils.get(interaction.guild.roles, name=x)
                if myrole in user.roles:
                    valid = True

    if user.guild_permissions.manage_guild == True or user.guild_permissions.administrator == True or str(user.id) == "215277233638604800":
        valid = True

    if valid == True:
        name = targetuser.name
        targetid = str(targetuser.id)
        if targetid in database:
            database[targetid]["account"] = accountname
            await interaction.response.send_message(f"Changed {name}'s account name to {accountname}")
            with open(guildstring, "w") as outfile:
                json.dump(database, outfile, indent = 4)

    else:
        await interaction.response.send_message(f"user not found in database")







client.run(BOT_TOKEN)
