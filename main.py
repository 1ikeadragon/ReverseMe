import discord
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API = "https://dogbolt.org/api/binaries/"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

def download_file(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {filename}: {e}")
        return None

@client.event
async def on_ready():
    print(f"Ready for decompilation as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user or not message.content.startswith(";revme"):
        return
    
    decompiler_requested = message.content.split()[1:] if len(message.content.split()) > 1 else []
    target_decompilers = {"binja": "BinaryNinja", "angr": "angr", "ghidra": "Ghidra", "hexrays": "Hex-Rays"}

    decompiler_filters = {
        name for key, name in target_decompilers.items()
        if not decompiler_requested or any(req in key for req in decompiler_requested)
    }

    if message.attachments:
        attachment = message.attachments[0]
        file_path = f"/tmp/{attachment.filename}"
        await attachment.save(file_path)
        
        with open(file_path, "rb") as binary:
            files = {"file": (attachment.filename, binary, "application/octet-stream")}
            response = requests.post(API, files=files)
        os.remove(file_path)

        if response.status_code == 201:
            decompilations_url = response.json().get("decompilations_url")
            decompilation_response = requests.get(decompilations_url)
            
            if decompilation_response.status_code == 200:
                results = decompilation_response.json().get("results", [])
                for item in results:
                    decompiler_name = item.get("decompiler", {}).get("name")
                    download_url = item.get("download_url")

                    if decompiler_name in decompiler_filters and download_url:
                        filename = f"{decompiler_name.replace(' ', '_')}.c"
                        downloaded_file = download_file(download_url, filename)
                        
                        if downloaded_file:
                            with open(downloaded_file, "r") as f:
                                code_content = f.read()

                                if len(code_content) <= 2000:
                                    await message.channel.send(
                                        f"**Decompilation from {decompiler_name}:**\n```c\n{code_content}\n```"
                                    )
                                else:
                                    await message.channel.send(
                                        f"**Decompilation from {decompiler_name}** (content too long):",
                                        file=discord.File(downloaded_file)
                                    )
                            os.remove(downloaded_file)
            else:
                await message.channel.send("Failed to retrieve decompilations.")
        else:
            await message.channel.send(f"Status Code: {response.status_code} - {response.text}")
    else:
        await message.channel.send("Please attach a file to be analyzed.")

client.run(DISCORD_TOKEN)
