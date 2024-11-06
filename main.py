import discord
from discord.ext import commands, tasks
import requests
import os
import logging
import random
from itertools import cycle
import subprocess

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)
bot_statuses = cycle(["Reversing with Binja", "Reversing with Angr", "Reversing with Ghidra", "Reversing with IDA"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(next(bot_statuses)))

async def save_attachment(attachment):
    temp_filename = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(10))
    file_path = f"/tmp/{temp_filename}"
    await attachment.save(file_path)
    logger.info(f"Saved attachment to {file_path}")
    return file_path

async def send_file_or_text(message, filename, content, lang=""):
    if len(content) <= 2000:
        await message.channel.send(f"**{filename}**:\n```{lang}\n{content}\n```")
    else:
        if "Hexdump" in filename:
            filename += ".hx"
        elif "asm" in lang:
            filename += ".x86asm"
        else:
            filename += ".c"
        
        with open(filename, "w") as file:
            file.write(content)
            
        await message.channel.send(file=discord.File(filename))
        os.remove(filename)

async def process_hex_dump(message, file_path):
    try:
        hex_output = subprocess.check_output(["xxd", file_path]).decode("utf-8")
        await send_file_or_text(message, "Hexdump", hex_output, "hx")
        logger.info("Sent hexdump.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate hexdump: {e}")
        await message.channel.send("Failed to generate hexdump.")

async def process_disassembly(message, file_path):
    try:
        asm_output = subprocess.check_output(["objdump", "-d", "-M", "intel", file_path]).decode("utf-8")
        await send_file_or_text(message, "Disassembly", asm_output, "x86asm")
        logger.info("Sent disassembly.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate disassembly: {e}")
        await message.channel.send("Failed to generate disassembly.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith(";revme help"):
        await message.channel.send(
            "Usage:\n"
            "1. Attach a file **MAX 2MB**.\n"
            "2. **DISABLED** Use `;revme` with decompiler names (e.g., `;revme binja/ghidra/ida/angr`) or no arguments to use all decompilers.\n"
            "See: [Note on Github](https://github.com/1ikeadragon/ReverseMe/issues/1)\n"
            "3. `;revme hex` for hex dump.\n"
            "4. `;revme asm` for disassembly.\n"
        )

    elif message.content.startswith(";revme hex") and message.attachments:
        file_path = await save_attachment(message.attachments[0])
        await process_hex_dump(message, file_path)
        os.remove(file_path)

    elif message.content.startswith(";revme asm") and message.attachments:
        file_path = await save_attachment(message.attachments[0])
        await process_disassembly(message, file_path)
        os.remove(file_path)

    elif message.content.startswith(";revme"):
        await message.channel.send(
        "Sorry! Decompilation **turned off temporarily!**\n"
        "See: [Note on Github](https://github.com/1ikeadragon/ReverseMe/issues/1)\n"
        "Use `;revme asm\\hex` for now :("
        )

    await bot.process_commands(message)

@bot.event
async def on_ready():
    logger.info(f"Bot ready as {bot.user}")
    change_bot_status.start()
    try:
        synced_commands = await bot.tree.sync()
        logger.info(f"Synced {len(synced_commands)} commands")
    except Exception as e:
        logger.error(f"Error while syncing slash command: {e}")

@bot.tree.command(name="invite", description="Generate an invite link for this bot.")
async def invite(interaction: discord.Interaction):
    permissions = discord.Permissions()
    permissions.update(
        send_messages=True,
        embed_links=True,
        attach_files=True,
        add_reactions=True,
        view_channel=True,
        read_message_history=True,
        send_messages_in_threads=True,
        use_slash_commands=True,
    )

    bot_invite_url = discord.utils.oauth_url(bot.user.id, permissions=permissions, scopes=["bot", "applications.commands"])
    await interaction.response.send_message(f"Invite me to your server using this link: {bot_invite_url}")

@bot.tree.command(name="ping", description="Ping the bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"{interaction.user.mention} pong!")

bot.run(DISCORD_TOKEN)
