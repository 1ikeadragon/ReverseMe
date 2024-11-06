import discord
from discord.ext import commands, tasks
import requests
import os
import logging
import random
from itertools import cycle
import subprocess

API = "https://dogbolt.org/api/binaries/"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DECOMPILERS = {"binja": "BinaryNinja", "angr": "angr", "ghidra": "Ghidra", "hexrays": "Hex-Rays"}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)
bot_statuses = cycle(["Reversing with Binja", "Reversing with Angr", "Reversing with Ghidra", "Reversing with IDA"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(next(bot_statuses)))

def download_file(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Downloaded file: {filename}")
        return filename
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading {filename}: {e}")
        return None

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

async def process_decompilation(message):
    await message.add_reaction("⏪")
    decompiler_requested = message.content.split()[1:] if len(message.content.split()) > 1 else []
    target_decompilers = {name for key, name in DECOMPILERS.items() if not decompiler_requested or key in decompiler_requested}

    if not message.attachments:
        await message.channel.send("Please attach a file to be analyzed.")
        await message.remove_reaction("⏪", bot.user)
        return

    attachment = message.attachments[0]
    file_path = await save_attachment(attachment)
    with open(file_path, "rb") as binary:
        response = requests.post(API, files={"file": (attachment.filename, binary, "application/octet-stream")})
    os.remove(file_path)
    logger.info(f"Sent file to API. Status code: {response.status_code}")

    if response.status_code == 429:
        await message.channel.send("Wait for 15 seconds, rate-limited by Dogbolt.")
        await message.remove_reaction("⏪", bot.user)
        return

    if response.status_code == 201:
        await handle_decompilation_results(message, response.json(), target_decompilers)
    else:
        await message.channel.send(f"API Error: Status Code {response.status_code}")
        await message.remove_reaction("⏪", bot.user)
        await message.add_reaction("❌")

async def handle_decompilation_results(message, response_json, target_decompilers):
    decompilations_url = response_json.get("decompilations_url")
    decompilation_response = requests.get(decompilations_url)

    if decompilation_response.status_code == 200:
        results = decompilation_response.json().get("results", [])
        for item in results:
            decompiler_name = item.get("decompiler", {}).get("name")
            download_url = item.get("download_url")
            error_message = item.get("error", "")

            if decompiler_name in target_decompilers:
                if error_message:
                    await message.reply(f"{decompiler_name} failed: {error_message}")
                    logger.error(f"{decompiler_name} error: {error_message}")
                elif download_url:
                    filename = f"{decompiler_name.replace(' ', '_')}.c"
                    downloaded_file = download_file(download_url, filename)
                    if downloaded_file:
                        await send_file_or_text(message, f"Decompilation from {decompiler_name}", open(downloaded_file).read(), "c")
                        os.remove(downloaded_file)
        await message.add_reaction("✅")
    else:
        await message.channel.send("Failed to retrieve decompilations.")
        await message.add_reaction("❌")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith(";revme help"):
        await message.channel.send(
            "Usage:\n"
            "1. Attach a file **MAX 2MB**.\n"
            "2. Use `;revme` with decompiler names (e.g., `;revme binja`).\n"
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
        await process_decompilation(message)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"Bot ready as {bot.user}")
    change_bot_status.start()

@bot.tree.command(name="invite", description="Generate an invite link for this bot.")
async def invite(interaction: discord.Interaction):
    permissions = discord.Permissions(
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


bot.run(DISCORD_TOKEN)
