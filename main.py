import discord
import requests
import os
import logging
import random
import subprocess

API = "https://dogbolt.org/api/binaries/"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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

async def process_decompilation(message):
    await message.add_reaction("⏪") 
    logger.info(f"Processing decompilation request from {message.author} for message: {message.content}")

    decompiler_requested = message.content.split()[1:] if len(message.content.split()) > 1 else []
    target_decompilers = {"binja": "BinaryNinja", "angr": "angr", "ghidra": "Ghidra", "hexrays": "Hex-Rays"}

    decompiler_filters = {
        name for key, name in target_decompilers.items()
        if not decompiler_requested or any(req in key for req in decompiler_requested)
    }

    if not message.attachments:
        await message.channel.send("Please attach a file to be analyzed.")
        await message.remove_reaction("⏪", client.user)
        return

    attachment = message.attachments[0]
    attachment.filename = ''.join(chr(random.randrange(65,90)) for i in range(10))
    file_path = f"/tmp/{attachment.filename}"
    await attachment.save(file_path)
    logger.info(f"Saved attachment to {file_path}")
    
    with open(file_path, "rb") as binary:
        files = {"file": (attachment.filename, binary, "application/octet-stream")}
        response = requests.post(API, files=files)
    os.remove(file_path)
    logger.info(f"Sent file to API. Status code: {response.status_code}")

    if response.status_code == 429:
        await message.channel.send("Wait for 15 seconds, rate-limited by Dogbolt.")
        await message.remove_reaction("⏪", client.user)
        return

    if response.status_code == 201:
        decompilations_url = response.json().get("decompilations_url")
        decompilation_response = requests.get(decompilations_url)
        
        if decompilation_response.status_code == 200:
            results = decompilation_response.json().get("results", [])
            sent_decompilers = set()  
            logger.info("Processing decompilation results.")

            for item in results:
                decompiler_name = item.get("decompiler", {}).get("name")
                download_url = item.get("download_url")
                error_message = item.get("error", "")

                if decompiler_name in decompiler_filters:
                    if error_message:
                        await message.reply(f"{decompiler_name} failed to decompile. Error: {error_message}")
                        await message.remove_reaction("⏪", client.user)
                        await message.add_reaction("❌")  
                        logger.error(f"{decompiler_name} error during decompilation: {error_message}")
                    elif download_url:
                        filename = f"{decompiler_name.replace(' ', '_')}.c"
                        downloaded_file = download_file(download_url, filename)
                        sent_decompilers.add(decompiler_name)

                        if downloaded_file:
                            with open(downloaded_file, "r") as f:
                                code_content = f.read()

                            if len(code_content) <= 2000:
                                await message.channel.send(
                                    f"**Decompilation from {decompiler_name}:**\n```c\n{code_content}\n```"
                                )
                            else:
                                await message.channel.send(
                                    f"**Decompilation from {decompiler_name}**:",
                                    file=discord.File(downloaded_file)
                                )
                            os.remove(downloaded_file)
                            logger.info(f"Sent decompilation result from {decompiler_name}.")
                            await message.remove_reaction("⏪", client.user)
                            await message.add_reaction("✅")  
                            logger.info("Decompilation process completed successfully.")
            
        else:
            await message.channel.send("Failed to retrieve decompilations.")
            await message.remove_reaction("⏪", client.user)
            await message.add_reaction("❌")  
            logger.error("Failed to retrieve decompilations from API.")
    else:
        await message.channel.send(f"Status Code: {response.status_code} - {response.text}")
        await message.remove_reaction("⏪", client.user)
        await message.add_reaction("❌")
        logger.error(f"API error: {response.status_code} - {response.text}")

async def process_hex_dump(message, file_path):
    try:
        hex_output = subprocess.check_output(["xxd", file_path]).decode("utf-8")
        if len(hex_output) <= 2000:
            await message.channel.send(f"**Hexdump of {os.path.basename(file_path)}:**\n```\n{hex_output}\n```")
        else:
            hex_filename = f"{os.path.basename(file_path)}_hexdump.txt"
            with open(hex_filename, "w") as hex_file:
                hex_file.write(hex_output)
            await message.channel.send(
                f"**Hexdump of {os.path.basename(file_path)}**:",
                file=discord.File(hex_filename)
            )
            os.remove(hex_filename)
        logger.info("Sent hexdump.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate hexdump: {e}")
        await message.channel.send("Failed to generate hexdump.")
    except Exception as e:
        logger.error(f"Unexpected error during hexdump: {e}")
        await message.channel.send("An error occurred while generating the hexdump.")

async def process_disassembly(message, file_path):
    try:
        asm_output = subprocess.check_output(["objdump", "-d", "-M", "intel", file_path]).decode("utf-8")
        if len(asm_output) <= 2000:
            await message.channel.send(f"**Disassembly of {os.path.basename(file_path)}:**\n```asm\n{asm_output}\n```")
        else:
            asm_filename = f"{os.path.basename(file_path)}_disassembly.asm"
            with open(asm_filename, "w") as asm_file:
                asm_file.write(asm_output)
            
            await message.channel.send(
                f"**Disassembly of {os.path.basename(file_path)}**:",
                file=discord.File(asm_filename)
            )
            os.remove(asm_filename)
        logger.info("Sent disassembly.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate disassembly: {e}")
        await message.channel.send("Failed to generate disassembly.")
    except Exception as e:
        logger.error(f"Unexpected error during disassembly: {e}")
        await message.channel.send("An error occurred while generating the disassembly.")

@client.event
async def on_ready():
    logger.info(f"Bot ready and logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(";revme help"):
        help_text = (
            "Usage:\n"
            "1. Attach a file **MAX 2MB** to be analyzed.\n"
            "2. Use `;revme` followed by one or more decompiler names to specify which decompilers to use.\n"
            "   - Available decompilers: `binja`, `ghidra`, `hexrays`, `angr`\n"
            "3. Example command: `;revme binja`\n"
            "4. Use `;revme hex` to print hex dump of the file.\n"
            "5. Use `;revme asm` to print disassembly of the file.\n\n"
            "The bot will process your request and return the decompiled code."
        )
        await message.channel.send(help_text)
        return

    if message.content.startswith(";revme hex") and message.attachments:
        attachment = message.attachments[0]
        file_path = f"/tmp/{attachment.filename}"
        await attachment.save(file_path)
        await process_hex_dump(message, file_path)
        os.remove(file_path)

    elif message.content.startswith(";revme asm") and message.attachments:
        attachment = message.attachments[0]
        file_path = f"/tmp/{attachment.filename}"
        await attachment.save(file_path)
        await process_disassembly(message, file_path)
        os.remove(file_path)

    elif message.content.startswith(";revme"):
        await process_decompilation(message)

@client.event
async def on_message_edit(before, after):
    if after.author == client.user or not after.content.startswith(";revme") or before.content == after.content:
        return
    await process_decompilation(after)

client.run(DISCORD_TOKEN)
