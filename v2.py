# === Your original imports stay unchanged ===
import random
import logging
import subprocess
import sys
import os
import re
import time
import concurrent.futures
import discord
from discord.ext import commands, tasks
import docker
import asyncio
from discord import app_commands
from discord.ui import Button, View, Select
import string
from datetime import datetime, timedelta
from typing import Optional, Literal

TOKEN = ''
RAM_LIMIT = '6g'
SERVER_LIMIT = 1
database_file = 'database.txt'
PUBLIC_IP = '138.68.79.95'

# Admin user IDs
ADMIN_IDS = [1368602087520473140]

intents = discord.Intents.default()
intents.messages = False
intents.message_content = False
bot = commands.Bot(command_prefix='/', intents=intents)
client = docker.from_env()


# ===============================
# Helpers
# ===============================

def parse_database_line(line):
    parts = line.strip().split('|')
    while len(parts) < 9:
        parts.append(None)
    return parts

def add_to_database(user, container_name, ssh_command, ram_limit=None, cpu_limit=None,
                    creator=None, expiry=None, os_type="Ubuntu 22.04", fake_ram=None):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram_limit or '2048'}|"
                f"{cpu_limit or '1'}|{creator or user}|{os_type}|{expiry or 'None'}|"
                f"{fake_ram or ram_limit}\n")

async def inject_fake_ram(container_name, fake_ram):
    script = f"""#!/bin/bash
echo "              total        used        free      shared  buff/cache   available"
echo "Mem:       {fake_ram}G      0G      {fake_ram}G      0G      0G      {fake_ram}G\""""
    await asyncio.create_subprocess_exec("docker", "exec", container_name, "bash", "-c",
        f"echo '{script}' > /usr/local/bin/free && chmod +x /usr/local/bin/free")

    await asyncio.create_subprocess_exec("docker", "exec", container_name, "bash", "-c",
        f"echo '#!/bin/bash\necho \"Mem: {fake_ram}G\"' > /usr/local/bin/lscpu && chmod +x /usr/local/bin/lscpu")

    await asyncio.create_subprocess_exec("docker", "exec", container_name, "bash", "-c",
        f"echo '#!/bin/bash\necho \"Memory: {fake_ram}GiB / {fake_ram}GiB\"' > /usr/local/bin/neofetch && chmod +x /usr/local/bin/neofetch")

    await asyncio.create_subprocess_exec("docker", "exec", container_name, "bash", "-c",
        f"echo '#!/bin/bash\necho \"Memory: {fake_ram}GiB / {fake_ram}GiB\"' > /usr/local/bin/fastfetch && chmod +x /usr/local/bin/fastfetch")


# ===============================
# New admin-only command
# ===============================
@bot.tree.command(name="secratespecs", description="🚀 Admin: Deploy VPS with fake RAM shown inside")
@app_commands.describe(
    real_ram="Actual RAM in GB",
    fake_ram="Fake RAM in GB shown inside",
    cpu="CPU cores",
    target_user="Discord user ID",
    container_name="Custom container name",
    expiry="Time until expiry"
)
async def secratespecs(interaction: discord.Interaction, real_ram: int, fake_ram: int,
                       cpu: int = 2, target_user: str = None, container_name: str = None, expiry: str = None):
    if interaction.user.id not in ADMIN_IDS:
        embed = discord.Embed(title="❌ Access Denied",
                              description="You don't have permission to use this command.",
                              color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    user_id = target_user if target_user else str(interaction.user.id)
    user = target_user if target_user else str(interaction.user)

    if not container_name:
        username = interaction.user.name.replace(" ", "_")
        container_name = f"VPS_{username}_{''.join(random.choices(string.ascii_letters+string.digits, k=6))}"

    # expiry parsing
    expiry_date = None
    if expiry:
        units = {'s':1,'m':60,'h':3600,'d':86400,'M':2592000,'y':31536000}
        unit = expiry[-1]
        if unit in units and expiry[:-1].isdigit():
            expiry_seconds = int(expiry[:-1]) * units[unit]
            expiry_date = (datetime.now() + timedelta(seconds=expiry_seconds)).strftime("%Y-%m-%d %H:%M:%S")

    embed = discord.Embed(
        title="⚙️ Creating Secret Specs VPS",
        description=f"**Real RAM:** {real_ram}GB\n**Fake RAM:** {fake_ram}GB\n**CPU:** {cpu} cores\n**Expiry:** {expiry_date or 'None'}",
        color=0x2400ff
    )
    await interaction.response.send_message(embed=embed)

    image = "ubuntu-22.04-with-tmate"
    try:
        container_id = subprocess.check_output([
            "docker", "run", "-itd", "--privileged", "--cap-add=ALL",
            f"--memory={real_ram}g", f"--cpus={cpu}", "--name", container_name, image
        ]).strip().decode('utf-8')
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"❌ Failed: {e}")
        return

    exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_name, "tmate", "-F",
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    ssh_session_line = await capture_ssh_session_line(exec_cmd)
    if not ssh_session_line:
        await interaction.followup.send("❌ Failed to start SSH session.")
        return

    add_to_database(user, container_name, ssh_session_line, ram_limit=real_ram, cpu_limit=cpu,
                    creator=str(interaction.user), expiry=expiry_date, os_type="Ubuntu 22.04", fake_ram=fake_ram)

    await inject_fake_ram(container_name, fake_ram)

    target_user_obj = await bot.fetch_user(int(user_id))
    try:
        dm_embed = discord.Embed(title="✅ Secret Specs VPS Created",
                                 description="Your VPS is ready with fake RAM specs.",
                                 color=0x2400ff)
        dm_embed.add_field(name="🔑 SSH Command", value=f"```{ssh_session_line}```", inline=False)
        dm_embed.add_field(name="💾 Real RAM", value=f"{real_ram}GB", inline=True)
        dm_embed.add_field(name="🎭 Fake RAM", value=f"{fake_ram}GB", inline=True)
        dm_embed.add_field(name="🔥 CPU", value=f"{cpu} cores", inline=True)
        await target_user_obj.send(embed=dm_embed)
    except:
        await interaction.followup.send("⚠️ Could not DM user, but VPS was created.")


# ===============================
# PATCHES in your existing commands
# ===============================
# In /list and /nodedmin:
# Replace:
#   parts = server.split('|')
#   ram = parts[3]
# With:
#   parts = parse_database_line(server)
#   ram = parts[8] if parts[8] else parts[3]

# In /regen-ssh, /restart, /start:
# After ssh_session_line is captured and before sending response, add:
#   with open(database_file, 'r') as f:
#       lines = f.readlines()
#   for line in lines:
#       parts = parse_database_line(line)
#       if parts[1] == container_name:
#           if parts[8]:
#               await inject_fake_ram(container_name, parts[8])
#           break


# === your remaining old code continues unchanged ===
bot.run(TOKEN)
