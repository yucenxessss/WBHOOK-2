import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import requests
import json

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

# ─── Logging Function via Webhook ─────────────────────────────
LOG_WEBHOOK_URL = "https://discord.com/api/webhooks/1376243189228245146/nIdSxbBw1ihf7kljfF0qryCwRuMK1IM0_rLwlMnJfIt7jrOZNKjX3sxH5uUDvWa26FhM"  # <-- Put your webhook URL here

async def log_command_usage(interaction: discord.Interaction, command_name: str):
    embed = {
        "title": "BOT LOGS",
        "color": 7506394,  # discord.Color.blurple()
        "timestamp": interaction.created_at.isoformat(),
        "fields": [
            {"name": "User", "value": f"(`{interaction.user.id}`)", "inline": False},
            {"name": "Command", "value": f"`/{command_name}`", "inline": False},
            {"name": "Add Bot Here","value": "[Add Bot](https://discord.com/oauth2/authorize?client_id=1355440307117752491&permissions=8&integration_type=0&scope=bot)", "inline": True},
            {"name": "On Bot", "value": "[Click Here](https://arzconicmgui.onrender.com/)", "inline": True},
        ],
        "thumbnail": {"url": interaction.user.avatar.url if interaction.user.avatar else ""}
    }

    data = {
        "embeds": [embed]
    }

    loop = asyncio.get_event_loop()
    def send_webhook():
        headers = {"Content-Type": "application/json"}
        requests.post(LOG_WEBHOOK_URL, data=json.dumps(data), headers=headers)

    await loop.run_in_executor(None, send_webhook)

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
