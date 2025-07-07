from keep_alive import keep_alive
keep_alive()
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import json
import aiohttp
import urllib.parse
import asyncio
from discord.ui import View, Button
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import shutil
import zipfile
import io
from discord.ui import View, Button, Select
from discord import SelectOption
from typing import List, Dict, Union
from volume_helper import get_volume_path

def is_admin_or_developer(ctx):
    return ctx.author.id == 514078286146699265 or ctx.author.guild_permissions.administrator

async def is_valid_word(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return False
            try:
                data = await response.json()
                return isinstance(data, list) and isinstance(data[0], dict) and "meanings" in data[0]
            except Exception:
                return False




class HelpMenuView(View):
    def __init__(self, embeds):
        super().__init__()
        self.embeds = embeds
        self.current_page = 0

    @discord.ui.button(label="🔄 Switch Section", style=discord.ButtonStyle.green)
    async def switch_section(self, interaction: discord.Interaction, button: Button):
        # Toggle between pages (0 and 1)
        self.current_page = 1 - self.current_page
        embed = self.embeds[self.current_page]
        await interaction.response.edit_message(embed=embed, view=self)

class LongestWordsView(View):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.current_page = 0


    async def update_embed(self, interaction):
        embed = discord.Embed(
            title="🔠 Longest Words Leaderboard",
            description=self.pages[self.current_page],
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏪ Previous", style=discord.ButtonStyle.blurple)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏩ Next", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

class AZView(View):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.current_page = 0

    async def update_embed(self, interaction):
        embed = discord.Embed(
            title="🔤 A-Z Letter Usage",
            description=self.pages[self.current_page],
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏪ Previous", style=discord.ButtonStyle.blurple)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏩ Next", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

class LyricsPaginator(View):
    def __init__(self, pages, title):
        super().__init__(timeout=800)
        self.pages = pages
        self.title = title
        self.current_page = 0

    async def update_embed(self, interaction):
        embed = discord.Embed(
            title=f"{self.title} (Page {self.current_page + 1}/{len(self.pages)})",
            description=self.pages[self.current_page],
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏪ Previous", style=discord.ButtonStyle.blurple)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏩ Next", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

def prune_old_entries(stats_path, max_age_days=180):
    stats = load_json(stats_path)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)

    if cutoff > now:
        print("⚠️ Cutoff date is in the future. Aborting prune.")
        return 0

    total_removed = 0
    new_stats = {}

    for guild_id, entries in stats.items():
        valid_entries = []
        removed = 0

        for entry in entries:
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts > now:
                    # Skip entries from the future
                    continue
                if ts >= cutoff:
                    valid_entries.append(entry)
                else:
                    removed += 1
            except Exception:
                # Skip if timestamp is malformed
                continue

        total_removed += removed
        new_stats[guild_id] = valid_entries

    if total_removed > 0:
        save_json(stats_path, new_stats)

    return total_removed

async def auto_prune():
    await bot.wait_until_ready()
    while not bot.is_closed():
        removed_count = prune_old_entries(STATS_FILE, max_age_days=180)
        # Optionally log the result:
        print(f"🧹 Auto-prune: removed {removed_count} word entries older than 180 days.")
        await asyncio.sleep(86400)


def deep_set(d, keys, value):
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def parse_value(raw: str):
    lowered = raw.lower()
    if lowered == "true": return True
    if lowered == "false": return False
    if lowered == "null": return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
lastfm_api_key = os.getenv('LASTFM_API_KEY')
mw_dict_key = os.getenv("MW_DICT_KEY")



if not token or not lastfm_api_key:
    raise ValueError("❌ Missing DISCORD_TOKEN or LASTFM_API_KEY in .env")

from volume_helper import get_volume_path

USER_FILE = get_volume_path("lastfm_users.json")
CHANNEL_FILE = get_volume_path("game_channels.json")
STATS_FILE = get_volume_path("word_stats.json")
UPDATE_FILE = get_volume_path("last_update.json")
LAST_LETTER_GAME_FILE = get_volume_path("last_letter_game.json")

log_path = get_volume_path("discord.log")
handler = logging.FileHandler(filename=log_path, encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.emojis_and_stickers = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")
file_lock = asyncio.Lock()

def load_user_data():
    try:
        with open(USER_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

async def save_user_data(data):
    async with file_lock:
        with open(USER_FILE, "w") as f:
            json.dump(data, f, indent=4)

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_update_times():
    return load_json(UPDATE_FILE)

def save_update_times(data):
    save_json(UPDATE_FILE, data)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"we are ready, {bot.user.name}")
    bot.loop.create_task(auto_prune())

@bot.command()
async def setlastfm(ctx, username: str):
    data = load_user_data()
    data[str(ctx.author.id)] = username
    await save_user_data(data)
    await ctx.send(f"✅ Saved your Last.fm username as **{username}**.")

@bot.command()
async def removelastfm(ctx):
    data = load_user_data()
    user_id = str(ctx.author.id)

    if user_id in data:
        del data[user_id]
        await save_user_data(data)
        await ctx.send("✅ Your Last.fm account has been removed from the bot.")
    else:
        await ctx.send("❌ You don't have a Last.fm account saved.")


@bot.command()
async def np(ctx, *, target: str = None):
    data = load_user_data()

    if target and ctx.message.mentions:
        mentioned_user = ctx.message.mentions[0]
        user_id = str(mentioned_user.id)
        if user_id in data:
            username = data[user_id]
        else:
            await ctx.send(f"❌ {mentioned_user.display_name} has not set their Last.fm username.")
            return
    elif target:
        username = target
    else:
        user_id = str(ctx.author.id)
        if user_id not in data:
            await ctx.send("❌ You haven't set your Last.fm username yet. Use !setlastfm <your_username>.")
            return
        username = data[user_id]

    api_key = lastfm_api_key
    url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={api_key}&format=json&limit=1"

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Cyboogie/1.0"}
            async with session.get(url, headers=headers) as response:
                # Log the raw response for debugging
                if response.status != 200:
                    await ctx.send(f"❌ Error fetching data from Last.fm. Status code: {response.status}")
                    return

                api_data = await response.json()
                # Log API response to debug
                print(f"API Response: {api_data}")

                # Check if Last.fm API returned an error
                if 'error' in api_data:
                    await ctx.send(f"❌ Last.fm API error: {api_data['error']}")
                    return

              
                track = api_data['recenttracks']['track'][0]
                artist = track['artist']['#text']
                song = track['name']
                album = track['album']['#text']
                now_playing = track.get('@attr', {}).get('nowplaying', False)

                # Image URL for cover art
                images = track.get('image', [])
                cover_url = next((img['#text'] for img in reversed(images) if img['#text']), None)

                embed = discord.Embed(
                    title=f"{'▶️ Now Playing' if now_playing else '⏹️ Last Played'}",
                    description=f"**{song}** by **{artist}**",
                    color=discord.Color.dark_purple()
                )
                embed.set_author(name=f"🎧 {username}")
                if album:
                    embed.add_field(name="Album", value=album, inline=False)
                if cover_url:
                    embed.set_thumbnail(url=cover_url)

                await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ An error occurred while fetching data from Last.fm: {str(e)}")
        print(f"Error fetching data for {username}: {str(e)}")


@bot.command()
async def nps(ctx):
    data = load_user_data()
    if not data:
        await ctx.send("❌ No users have set their Last.fm usernames yet.")
        return

    embed = discord.Embed(title="🎵 Now Playing Server", color=discord.Color.blurple())
    embed.set_footer(text="Data fetched from Last.fm")

    api_key = lastfm_api_key

    async with aiohttp.ClientSession() as session:
        found_anyone = False

        for user_id, lastfm_username in data.items():
            member = ctx.guild.get_member(int(user_id))
            if not member:
                continue

            display_name = member.display_name
            url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={lastfm_username}&api_key={api_key}&format=json&limit=1"

            try:
                headers = {"User-Agent": "Cyboogie/1.0"}
                async with session.get(url, headers=headers) as response:
                    user_data = await response.json()

                track = user_data['recenttracks']['track'][0]
                artist = track['artist']['#text']
                song = track['name']
                now_playing = track.get('@attr', {}).get('nowplaying', False)

                status = "▶️ Now Playing" if now_playing else "⏹️ Last Played"
                embed.add_field(
                    name=f"{display_name} ({lastfm_username})",
                    value=f"{status}: **{song}** by **{artist}**",
                    inline=False
                )
                found_anyone = True
            except Exception:
                embed.add_field(
                    name=f"{display_name} ({lastfm_username})",
                    value="⚠️ Error fetching data",
                    inline=False
                )

        if not found_anyone:
            await ctx.send("🤷 Nobody in this server has set a Last.fm username yet.")
            return

    await ctx.send(embed=embed)

@bot.command(name="alllastfm")
async def alllastfm(ctx):
    """List all server members who have registered a Last.fm username."""
    data = load_user_data()
    if not data:
        await ctx.send("No users have registered a Last.fm username.")
        return
        

@bot.command()
async def lyr(ctx, *, query: str = None):
    data = load_user_data()
    api_key = os.getenv('LASTFM_API_KEY')

    # Handle input
    if query:
        if '-' in query:
            artist, song = [x.strip() for x in query.split('-', 1)]
            cover_url = None
            source = "manual"
        else:
            await ctx.send("❌ Please provide the song in Artist - Song format (e.g., !lyr Daft Punk - Around the World).")
            return
    else:
        # Last.fm fallback if no query
        user_id = str(ctx.author.id)
        if user_id not in data:
            await ctx.send("❌ You haven't set your Last.fm username yet. Use !setlastfm <your_username>.")
            return

        username = data[user_id]
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={api_key}&format=json&limit=1"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await ctx.send("❌ Failed to fetch your recent track from Last.fm.")
                    return
                api_data = await response.json()

        try:
            track = api_data['recenttracks']['track'][0]
            artist = track['artist']['#text']
            song = track['name']
            images = track.get('image', [])
            cover_url = next((img['#text'] for img in reversed(images) if img['#text']), None)
            source = f"Last.fm user: {username}"
        except (KeyError, IndexError):
            await ctx.send("⚠️ Couldn't fetch your currently playing track.")
            return

    # Clean artist and song without changing case
    artist = artist.strip()
    song = song.strip()

    # Remove live suffixes (case insensitive)
    live_variants = [" (Live)", "- Live", "[Live]"]
    for variant in live_variants:
        song = song.replace(variant, "", 1).strip()

    # Query lyrics.ovh
    api_url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(song)}"

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status != 200:
                await ctx.send(f"❌ Couldn't fetch lyrics for `{artist} - {song}`. Please double-check the names or use `!lyr Artist - Song`.")
                return
            lyrics_data = await response.json()
            lyrics = lyrics_data.get('lyrics')

    if not lyrics:
        await ctx.send(f"❌ No lyrics found for `{song}` by `{artist}`.")
        return

    # Clean lyrics
    cleaned_lyrics = "\n".join(line.strip() for line in lyrics.splitlines() if line.strip())
    max_length = 2000
    pages = [cleaned_lyrics[i:i + max_length] for i in range(0, len(cleaned_lyrics), max_length)]

    # Create embed
    embed = discord.Embed(
        title=f"🎶 Lyrics: {song}",
        description=pages[0],
        color=discord.Color.green()
    )
    embed.set_author(name=f"By {artist}")
    embed.set_footer(text=f"{source} • Page 1/{len(pages)}")

    if cover_url:
        embed.set_thumbnail(url=cover_url)

    view = LyricsPaginator(pages, f"🎶 Lyrics: {song} by {artist}")
    await ctx.send(embed=embed, view=view)




@bot.command()
async def setchannel(ctx):
    if not is_admin_or_developer(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return

    data = load_json(CHANNEL_FILE)
    data[str(ctx.guild.id)] = ctx.channel.id
    save_json(CHANNEL_FILE, data)
    await ctx.send(f"✅ This channel (`{ctx.channel.name}`) is now set as the game channel.")


@bot.command()
async def scanchannel(ctx):
    if not is_admin_or_developer(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return

    channel_map = load_json(CHANNEL_FILE)
    guild_id = str(ctx.guild.id)
    channel_id = channel_map.get(guild_id)

    if not channel_id:
        await ctx.send("❌ No channel has been set. Use `!setchannel` first.")
        return

    try:
        channel = await bot.fetch_channel(channel_id)
    except discord.NotFound:
        await ctx.send("❌ Could not find the game channel.")
        return

    days = 180

    stats = load_json(STATS_FILE)
    guild_stats = []

    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    await ctx.send(f"Scanning the game channel for messages from the last {days} days...")

    async for message in channel.history(limit=None, after=start_time, oldest_first=True):
        if message.author.bot or not message.content.strip():
            continue

        words = [
            w.strip('.,!?()[]{}<>"\'')
            for w in message.content.split()
            if w.isalpha()
        ]

        if words:
            word = words[0]
            guild_stats.append({
                "user_id": message.author.id,
                "username": message.author.display_name,
                "word": word,
                "length": len(word),
                "timestamp": message.created_at.isoformat()
            })

    stats[guild_id] = guild_stats
    save_json(STATS_FILE, stats)

    update_times = load_update_times()
    update_times[guild_id] = datetime.now(timezone.utc).isoformat()
    save_update_times(update_times)

    await ctx.send(f"✅ Done! Collected {len(guild_stats)} word entries from `{channel.name}`.")


@bot.command()
async def clearchannel(ctx):
    if not is_admin_or_developer(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return

    stats = load_json(STATS_FILE)
    guild_id = str(ctx.guild.id)

    if guild_id in stats:
        del stats[guild_id]
        save_json(STATS_FILE, stats)
        await ctx.send("Word stats cleared for this server, RIP!.")
    else:
        await ctx.send("No stats found to clear for this server.")



@bot.command()
async def uc(ctx):
    guild_id = str(ctx.guild.id)
    channel_map = load_json(CHANNEL_FILE)
    update_times = load_update_times()
    stats = load_json(STATS_FILE)

    channel_id = channel_map.get(guild_id)
    if not channel_id:
        await ctx.send("No game channel set. Use `!setchannel` first.")
        return

    try:
        channel = await bot.fetch_channel(channel_id)
    except discord.NotFound:
        await ctx.send("Could not find the game channel.")
        return

    last_update_str = update_times.get(guild_id)
    if last_update_str:
        after_time = datetime.fromisoformat(last_update_str.replace("Z", "+00:00"))
    else:
        after_time = datetime.now(timezone.utc) - timedelta(days=90)

    await ctx.send("Updating word stats from the last letter channel...")

    new_stats = stats.get(guild_id, [])
    scanned_count = 0

    async for message in channel.history(limit=None, after=after_time, oldest_first=True):
        if message.author.bot or not message.content.strip():
            continue

        words = [
            w.strip('.,!?()[]{}<>"\'')
            for w in message.content.split()
            if w.isalpha()
        ]

        if words:
            word = words[0]
            new_stats.append({
                "user_id": message.author.id,
                "username": message.author.display_name,
                "word": word,
                "length": len(word),
                "timestamp": message.created_at.isoformat()
            })
            scanned_count += 1

    stats[guild_id] = new_stats
    save_json(STATS_FILE, stats)
    update_times[guild_id] = datetime.now(timezone.utc).isoformat()
    save_update_times(update_times)

    await ctx.send(f"Update complete! **{scanned_count}** new words added.")


@bot.command()
async def totalwords(ctx, period: str = "all"):
    """
    Show the total word count for this server.
    Optional period: 7d, 30d, 90d, or all (default: all).
    """
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("❌ Invalid period. Use one of: `7d`, `30d`, `90d`, `all`.")
        return

    stats = load_json(STATS_FILE)
    guild_id = str(ctx.guild.id)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("ℹ No word stats available for this server yet.")
        return

    cutoff = datetime.now(timezone.utc) - period_map[period] if period_map[period] else None

    filtered = [
        entry for entry in guild_stats
        if not cutoff or datetime.fromisoformat(entry["timestamp"]) >= cutoff
    ]

    word_count = len(filtered)

    await ctx.send(f"Total words collected for this server ({period}): **{word_count}**")

@bot.command()
async def tw(ctx, period: str = "all"):
    """
    Show the total word count for this server.
    Optional period: 7d, 30d, 90d, or all (default: all).
    """
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("❌ Invalid period. Use one of: `7d`, `30d`, `90d`, `all`.")
        return

    stats = load_json(STATS_FILE)
    guild_id = str(ctx.guild.id)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("ℹ No word stats available for this server yet.")
        return

    cutoff = datetime.now(timezone.utc) - period_map[period] if period_map[period] else None

    filtered = [
        entry for entry in guild_stats
        if not cutoff or datetime.fromisoformat(entry["timestamp"]) >= cutoff
    ]

    word_count = len(filtered)

    await ctx.send(f"Total words collected for this server ({period}): **{word_count}**")


@bot.command()
async def mostwords(ctx, period: str = None):
    """Show top 20 users who have sent the most words, with optional time period."""
    period_map = {
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
        'all': None
    }

    if period is None:
        # default to 180 days if no period is specified
        period = '180d'
        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    else:
        period = period.lower()
        if period not in period_map:
            await ctx.send("❌ Invalid choice. Use: `7d`, `30d`, `90d`, `all`.")
            return
        cutoff = datetime.now(timezone.utc) - period_map[period] if period_map[period] else None

    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("ℹ No stats available for this server yet.")
        return

    user_totals = defaultdict(int)

    for entry in guild_stats:
        ts = datetime.fromisoformat(entry["timestamp"])
        if cutoff and ts < cutoff:
            continue

        user_id = entry["user_id"]
        user_totals[user_id] += 1

    if not user_totals:
        await ctx.send("No data found for the selected period.")
        return

    sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)[:20]
    embed = discord.Embed(
        title=f"Top 20 Users by Word Count ({period})",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Period: {period} • Sorted by word count")

    for idx, (user_id, count) in enumerate(sorted_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else "Unknown User"
        embed.add_field(
            name=f"{idx}. {name}",
            value=f"Words: **{count}**",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
async def mw(ctx, period: str = None):
    """Show top 20 users who have sent the most words, with optional time period."""
    period_map = {
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
        'all': None
    }

    if period is None:
        # default to 180 days if no period is specified
        period = '180d'
        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    else:
        period = period.lower()
        if period not in period_map:
            await ctx.send("❌ Invalid choice. Use: `7d`, `30d`, `90d`, `all`.")
            return
        cutoff = datetime.now(timezone.utc) - period_map[period] if period_map[period] else None

    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("ℹ No stats available for this server yet.")
        return

    user_totals = defaultdict(int)

    for entry in guild_stats:
        ts = datetime.fromisoformat(entry["timestamp"])
        if cutoff and ts < cutoff:
            continue

        user_id = entry["user_id"]
        user_totals[user_id] += 1

    if not user_totals:
        await ctx.send("No data found for the selected period.")
        return

    sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)[:20]
    embed = discord.Embed(
        title=f"Top 20 Users by Word Count ({period})",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Period: {period} • Sorted by word count")

    for idx, (user_id, count) in enumerate(sorted_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else "Unknown User"
        embed.add_field(
            name=f"{idx}. {name}",
            value=f"Words: **{count}**",
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command()
async def lpw(ctx, period: str = "90d"):
    """
    Show the top 20 users with the highest average letters per word.
    Optional period: 7d, 30d, 90d, or 'all'.
    Users must meet minimum word counts:
    7d → 10, 30d → 20, 90d → 50, all → 100.
    """
    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("No word stats available for this server yet.")
        return

    now = datetime.now(timezone.utc)
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    min_words_map = {
        "7d": 10,
        "30d": 20,
        "90d": 50,
        "all": 100
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("Invalid period. Use one of: 7d, 30d, 90d, all.")
        return

    cutoff = now - period_map[period] if period_map[period] else None
    min_words = min_words_map[period]

    user_totals = defaultdict(lambda: {"letters": 0, "words": 0, "username": None})

    for entry in guild_stats:
        ts = datetime.fromisoformat(entry["timestamp"])
        if cutoff and ts < cutoff:
            continue

        user_id = entry["user_id"]
        username = entry["username"]
        word_length = entry["length"]

        user_totals[user_id]["letters"] += word_length
        user_totals[user_id]["words"] += 1
        user_totals[user_id]["username"] = username

    avg_list = []
    for user_id, data in user_totals.items():
        if data["words"] < min_words:
            continue  # skip users below threshold
        avg = data["letters"] / data["words"]
        avg_list.append((data["username"], avg, data["words"]))

    if not avg_list:
        await ctx.send(f"No data found for the selected period (min {min_words} words required).")
        return

    avg_list.sort(key=lambda x: x[1], reverse=True)
    top_users = avg_list[:20]

    embed = discord.Embed(
        title=f"Top 20 Users by Avg Letters Per Word ({period})",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Period: {period} • Min {min_words} words • Sorted by highest average")

    for idx, (username, avg, total_words) in enumerate(top_users, start=1):
        embed.add_field(
            name=f"{idx}. {username}",
            value=f"Avg Letters/Word: **{avg:.2f}** (Words: {total_words})",
            inline=False
        )

    await ctx.send(embed=embed)



@bot.command()
async def longestwords(ctx, period: str = "90d"):
    """
    Show the longest 100 words with usernames.
    Optional period: 7d, 30d, 90d, or 'all'.
    """
    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("No word stats available for this server yet.")
        return

    now = datetime.now(timezone.utc)
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("Invalid period. Use one of: 7d, 30d, 90d, all.")
        return

    cutoff = now - period_map[period] if period_map[period] else None

    word_user_count = defaultdict(lambda: defaultdict(int))  # word -> user_id -> count
    user_names = {}

    for entry in guild_stats:
        ts = datetime.fromisoformat(entry["timestamp"])
        if cutoff and ts < cutoff:
            continue

        word = entry["word"]
        user_id = entry["user_id"]
        username = entry["username"]

        word_user_count[word][user_id] += 1
        user_names[user_id] = username

    word_entries = []
    for word, users in word_user_count.items():
        for user_id, count in users.items():
            username = user_names[user_id]
            word_entries.append({
                "word": word,
                "length": len(word),
                "username": username,
                "count": count
            })

    if not word_entries:
        await ctx.send("No data found for the selected period.")
        return

    word_entries.sort(key=lambda x: x["length"], reverse=True)
    top_words = word_entries[:100]

    pages = []
    for i in range(0, len(top_words), 10):
        chunk = top_words[i:i+10]
        page_content = ""
        for idx, entry in enumerate(chunk, start=i+1):
            count_str = f" (x{entry['count']})" if entry['count'] > 1 else ""
            page_content += (
                f"**{idx}. {entry['word']}** ({entry['length']} letters)"
                f" — *{entry['username']}*{count_str}\n"
            )
        pages.append(page_content)

    embed = discord.Embed(
        title=f"🔠 Longest Words Leaderboard ({period})",
        description=pages[0],
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Page 1/{len(pages)}")

    view = LongestWordsView(pages)
    await ctx.send(embed=embed, view=view)


@bot.command()
async def lw(ctx, period: str = "90d"):
    """
    Show the longest 100 words with usernames.
    Optional period: 7d, 30d, 90d, or 'all'.
    """
    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("No word stats available for this server yet.")
        return

    now = datetime.now(timezone.utc)
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("Invalid period. Use one of: 7d, 30d, 90d, all.")
        return

    cutoff = now - period_map[period] if period_map[period] else None

    word_user_count = defaultdict(lambda: defaultdict(int))  # word -> user_id -> count
    user_names = {}

    for entry in guild_stats:
        ts = datetime.fromisoformat(entry["timestamp"])
        if cutoff and ts < cutoff:
            continue

        word = entry["word"]
        user_id = entry["user_id"]
        username = entry["username"]

        word_user_count[word][user_id] += 1
        user_names[user_id] = username

    word_entries = []
    for word, users in word_user_count.items():
        for user_id, count in users.items():
            username = user_names[user_id]
            word_entries.append({
                "word": word,
                "length": len(word),
                "username": username,
                "count": count
            })

    if not word_entries:
        await ctx.send("No data found for the selected period.")
        return

    word_entries.sort(key=lambda x: x["length"], reverse=True)
    top_words = word_entries[:100]

    pages = []
    for i in range(0, len(top_words), 10):
        chunk = top_words[i:i+10]
        page_content = ""
        for idx, entry in enumerate(chunk, start=i+1):
            count_str = f" (x{entry['count']})" if entry['count'] > 1 else ""
            page_content += (
                f"**{idx}. {entry['word']}** ({entry['length']} letters)"
                f" — *{entry['username']}*{count_str}\n"
            )
        pages.append(page_content)

    embed = discord.Embed(
        title=f"🔠 Longest Words Leaderboard ({period})",
        description=pages[0],
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Page 1/{len(pages)}")

    view = LongestWordsView(pages)
    await ctx.send(embed=embed, view=view)

@bot.command()
async def az(ctx, period: str = "90d"):
    """
    Show A-Z counts of how many words *start* with each letter (sorted by most-used first).
    Optional period: 7d, 30d, 90d, or 'all'.
    """
    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)
    guild_stats = stats.get(guild_id, [])

    if not guild_stats:
        await ctx.send("No word stats available for this server yet.")
        return

    now = datetime.now(timezone.utc)
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("Invalid period. Use one of: 7d, 30d, 90d, all.")
        return

    cutoff = now - period_map[period] if period_map[period] else None

    start_letter_counts = defaultdict(int)

    for entry in guild_stats:
        ts = datetime.fromisoformat(entry["timestamp"])
        if cutoff and ts < cutoff:
            continue

        word = entry["word"].lower()
        if word and word[0].isalpha():
            start_letter_counts[word[0]] += 1

    az_letters = [chr(i) for i in range(97, 123)]
    letter_stats = [(letter.upper(), start_letter_counts.get(letter, 0)) for letter in az_letters]
    letter_stats.sort(key=lambda x: (-x[1], x[0]))

    if all(count == 0 for _, count in letter_stats):
        await ctx.send("No data found for the selected period.")
        return

    pages = []
    for i in range(0, len(letter_stats), 10):
        chunk = letter_stats[i:i+10]
        page_content = ""
        for letter, count in chunk:
            page_content += f"**{letter}**: {count} words started with this letter\n"
        pages.append(page_content)

    embed = discord.Embed(
        title=f"🔤 A-Z Starting Letter Stats ({period})",
        description=pages[0],
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"Page 1/{len(pages)}")

    view = AZView(pages)
    await ctx.send(embed=embed, view=view)


@bot.command()
async def glb(ctx, period: str = "all"):
    """
    Show the global leaderboard of servers that have used the most words.
    Period: 7d, 30d, 90d, or all.
    """
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    if period not in period_map:
        await ctx.send("Invalid period. Use one of: `7d`, `30d`, `90d`, `all`.")
        return

    cutoff = datetime.now(timezone.utc) - period_map[period] if period_map[period] else None

    stats = load_json(STATS_FILE)
    server_stats = []

    for guild_id, guild_stats in stats.items():
        word_count = 0
        letter_count = 0

        guild = ctx.bot.get_guild(int(guild_id))
        server_name = guild.name if guild else f"Server {guild_id}"

        for entry in guild_stats:
            ts = datetime.fromisoformat(entry["timestamp"])
            if cutoff and ts < cutoff:
                continue

            word_count += 1
            letter_count += entry["length"]

        if word_count > 0:
            avg_letters = letter_count / word_count
            server_stats.append({
                "server_name": server_name,
                "word_count": word_count,
                "avg_letters": avg_letters
            })

    if not server_stats:
        await ctx.send(f"No data found for the selected period ({period}).")
        return

    server_stats.sort(key=lambda x: x["word_count"], reverse=True)

    pages = []
    max_per_page = 10
    for i in range(0, len(server_stats), max_per_page):
        chunk = server_stats[i:i + max_per_page]
        page_content = ""
        for idx, server in enumerate(chunk, start=i + 1):
            page_content += (
                f"**{idx}. {server['server_name']}** — "
                f"Words: **{server['word_count']}** | Avg Letters/Word: **{server['avg_letters']:.2f}**\n\n"
            )
        pages.append(page_content.strip())

    embed = discord.Embed(
        title=f"Global Server Leaderboard ({period})",
        description=pages[0],
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Page 1/{len(pages)}")

    view = GlobalLeaderboardView(pages)
    await ctx.send(embed=embed, view=view)



class GlobalLeaderboardView(View):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.current_page = 0

    async def update_embed(self, interaction):
        embed = discord.Embed(
            title=f"Global Leaderboard",
            description=self.pages[self.current_page],
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏪ Previous", style=discord.ButtonStyle.blurple)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏩ Next", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

@bot.command()
async def glbu(ctx, period: str = "all"):
    """
    Show the global leaderboard of users (top 100 total words).
    Period: 7d, 30d, 90d, or all (default).
    """
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    period = period.lower()
    if period not in period_map:
        await ctx.send("❌ Invalid period. Use one of: `7d`, `30d`, `90d`, `all`.")
        return

    stats = load_json(STATS_FILE)
    cutoff = datetime.now(timezone.utc) - period_map[period] if period_map[period] else None

    user_totals = {}

    for guild_stats in stats.values():
        for entry in guild_stats:
            ts = datetime.fromisoformat(entry["timestamp"])
            if cutoff and ts < cutoff:
                continue

            uid = entry["user_id"]
            if uid not in user_totals:
                user_obj = bot.get_user(int(uid))
                if not user_obj:
                    continue  # Skip deleted or unknown users
                uname = user_obj.name
                user_totals[uid] = {"username": uname, "count": 0, "letters": 0}

            user_totals[uid]["count"] += 1
            user_totals[uid]["letters"] += entry["length"]

    if not user_totals:
        await ctx.send(f"No global data found for period `{period}`.")
        return

    users = []
    for user in user_totals.values():
        avg_letters = user["letters"] / user["count"]
        users.append((user["username"], user["count"], avg_letters))

    users.sort(key=lambda x: x[1], reverse=True)
    top_users = users[:100]  # Limit to top 100

    pages = []
    per_page = 10
    for i in range(0, len(top_users), per_page):
        chunk = top_users[i:i + per_page]
        page = ""
        for idx, (uname, count, avg) in enumerate(chunk, start=i + 1):
            page += f"**{idx}. {uname}** — Words: **{count}** | Avg Letters/Word: **{avg:.2f}**\n\n"
        pages.append(page.strip())

    embed = discord.Embed(
        title=f"Global User Leaderboard ({period})",
        description=pages[0],
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Page 1/{len(pages)}")

    view = GlobalUserLeaderboardView(pages)
    await ctx.send(embed=embed, view=view)


class GlobalUserLeaderboardView(View):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.current = 0

    async def update_embed(self, interaction):
        embed = discord.Embed(
            title="Global User Leaderboard",
            description=self.pages[self.current],
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Page {self.current + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏪ Previous", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if self.current > 0:
            self.current -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏩ Next", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

@bot.command()
@commands.is_owner()
async def getjson(ctx, filename: str):
    """Send a JSON file from the Railway volume."""
    try:
        path = get_volume_path(filename)
        with open(path, "rb") as f:
            await ctx.send(file=discord.File(f, filename))
    except FileNotFoundError:
        await ctx.send("❌ File not found.")

@bot.command()
@commands.is_owner()
async def uploadjson(ctx, filename: str):
    """Upload a .json file to Railway volume via attachment."""
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach a .json file.")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.endswith(".json"):
        await ctx.send("❌ Only .json files are supported.")
        return

    path = get_volume_path(filename)
    if os.path.exists(path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{path}.bak_{timestamp}"
        shutil.copy(path, backup_path)

    await attachment.save(path)
    await ctx.send(f"✅ Uploaded `{filename}` to volume.")


@bot.command()
@commands.is_owner()
async def showjson(ctx, filename: str):
    """Show the contents of a JSON file (up to 1900 characters)."""
    path = get_volume_path(filename)
    if not os.path.exists(path):
        await ctx.send("❌ File not found.")
        return

    with open(path, "r") as f:
        try:
            contents = json.load(f)
        except json.JSONDecodeError:
            await ctx.send("⚠️ JSON file is not valid.")
            return

    text = json.dumps(contents, indent=2)
    if len(text) > 1900:
        await ctx.send("⚠️ File too large to display. Please use !getjson instead.")
    else:
        await ctx.send(f"```json\\n{text}```")

@bot.command()
@commands.is_owner()
async def getjsonzip(ctx, filename: str):
    """Send a zipped JSON file from the volume."""
    try:
        path = get_volume_path(filename)
        if not os.path.exists(path):
            await ctx.send("❌ File not found.")
            return

        # Create in-memory zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(path, arcname=filename)
        zip_buffer.seek(0)

        await ctx.send(file=discord.File(fp=zip_buffer, filename=f"{filename}.zip"))
    except Exception as e:
        await ctx.send(f"⚠️ Error zipping file: {e}")

@bot.command()
async def downloadstats(ctx):
    """
    Developer-only command to download word stats for the current server as a ZIP file.
    """
    if ctx.author.id != 514078286146699265:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    guild_id = str(ctx.guild.id)
    stats = load_json(STATS_FILE)

    if guild_id not in stats or not stats[guild_id]:
        await ctx.send("ℹ No word stats found for this server.")
        return

    # Create temp JSON content for this guild only
    import io
    import zipfile

    json_bytes = json.dumps({guild_id: stats[guild_id]}, indent=2).encode("utf-8")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"word_stats_{guild_id}.json", json_bytes)
    zip_buffer.seek(0)

    await ctx.send(file=discord.File(zip_buffer, filename=f"word_stats_{guild_id}.zip"))


# ========== LAST LETTER GAME COMMANDS ==========

@bot.command(name="startlastletter")
async def start_last_letter(ctx):
    if not is_admin_or_developer(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return

    data = load_json(LAST_LETTER_GAME_FILE)
    guild_id = str(ctx.guild.id)
    channel_id = ctx.channel.id

    data[guild_id] = {
        "channel_id": channel_id,
        "length": "all",
        "status": "active",
        "words_used": [],
        "participants": {},
        "last_word": None
    }
    save_json(LAST_LETTER_GAME_FILE, data)
    await ctx.send("✅ Last Letter Game started in this channel!")


@bot.command(name="endlastletter")
async def end_last_letter(ctx):
    if not is_admin_or_developer(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return

    data = load_json(LAST_LETTER_GAME_FILE)
    guild_id = str(ctx.guild.id)

    game = data.get(guild_id)
    if not game or game.get("status") != "active":
        await ctx.send("⚠️ No active game found.")
        return

    game["status"] = "ended"
    save_json(LAST_LETTER_GAME_FILE, data)

    stats = game.get("participants", {})
    if not stats:
        await ctx.send("❌ No participants or words were recorded.")
        return

    # Prepare leaderboard
    sorted_users = sorted(stats.items(), key=lambda x: x[1]["word_count"], reverse=True)
    embed = discord.Embed(
        title="Last Letter Game Ended — Final Leaderboard",
        color=discord.Color.gold()
    )
    for idx, (user_id, info) in enumerate(sorted_users, 1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        embed.add_field(
            name=f"{idx}. {name}",
            value=f"Words: **{info['word_count']}** • Letter Score: **{info['letter_score']}**",
            inline=False
        )

    await ctx.send(embed=embed)



@bot.command(name="changelength")
async def change_length(ctx):
    class LengthSelect(discord.ui.Select):
        def __init__(self):
            options = [SelectOption(label=str(i), value=str(i)) for i in range(3, 21)]
            options.append(SelectOption(label="All", value="all"))
            super().__init__(placeholder="Choose word length...", options=options)

        async def callback(self, interaction: discord.Interaction):
            data = load_json(LAST_LETTER_GAME_FILE)
            guild_id = str(ctx.guild.id)
            if guild_id not in data:
                await interaction.response.send_message("⚠️ No active game found.", ephemeral=True)
                return
            data[guild_id]["length"] = self.values[0]
            save_json(LAST_LETTER_GAME_FILE, data)
            await interaction.response.send_message(f"✅ Word length set to **{self.values[0]}**", ephemeral=True)

    class LengthView(View):
        def __init__(self):
            super().__init__()
            self.add_item(LengthSelect())

    await ctx.send("🔢 Select desired word length:", view=LengthView())


@bot.command(name="lastletter")
async def show_last_letter_status(ctx):
    data = load_json(LAST_LETTER_GAME_FILE)
    guild_id = str(ctx.guild.id)
    game = data.get(guild_id)

    if not game or game["status"] != "active":
        await ctx.send("⚠️ No active game found.")
        return

    channel = bot.get_channel(game["channel_id"])
    words_used = game.get("words_used", [])
    participants = game.get("participants", {})
    last_word = game.get("last_word") or "None"
    selected_length = game.get("length")

    embed = discord.Embed(
        title="🎮 Last Letter Game Status",
        color=discord.Color.blue()
    )
    embed.add_field(name="Status", value="✅ #1", inline=True)
    embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=True)
    embed.add_field(name="Selected Length", value=selected_length, inline=True)
    embed.add_field(name="Words Used", value=len(words_used), inline=True)
    embed.add_field(name="Participants", value=len(participants), inline=True)
    embed.add_field(name="Last Word", value=last_word, inline=False)

    class LeaderboardButton(discord.ui.View):
        def __init__(self, author_id):
            super().__init__(timeout=60)
            self.author_id = author_id

        @discord.ui.button(label="📈 Leaderboard", style=discord.ButtonStyle.green)
        async def show_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("❌ Only the command invoker can use this button.", ephemeral=True)
                return

            stats = game.get("participants", {})
            if not stats:
                await interaction.response.send_message("No leaderboard data yet.", ephemeral=True)
                return

            sorted_stats = sorted(stats.items(), key=lambda x: x[1]["word_count"], reverse=True)
            lb_embed = discord.Embed(
                title="📈 Current Leaderboard",
                color=discord.Color.green()
            )

            for idx, (uid, info) in enumerate(sorted_stats, 1):
                user = ctx.guild.get_member(int(uid))
                name = user.display_name if user else f"User {uid}"
                lb_embed.add_field(
                    name=f"{idx}. {name}",
                    value=f"Words: {info['word_count']} • Score: {info['letter_score']}",
                    inline=False
                )

            await interaction.response.send_message(embed=lb_embed)

    view = LeaderboardButton(author_id=ctx.author.id)
    await ctx.send(embed=embed, view=view)


@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot or not message.guild:
        return

    data = load_json(LAST_LETTER_GAME_FILE)
    guild_id = str(message.guild.id)
    game = data.get(guild_id)

    if not game or game.get("status") != "active":
        return

    if message.channel.id != game.get("channel_id"):
        return

    word = message.content.strip().lower()
    if not word.isalpha():
        await message.delete()
        return

    # Game state
    words_used = game.get("words_used", [])
    participants = game.get("participants", {})
    last_word = game.get("last_word")
    selected_length = game.get("length", "all")
    used_words_set = {entry["word"] for entry in words_used}

    # One user cannot play twice in a row
    if words_used and words_used[-1]["user_id"] == message.author.id:
        await message.delete()
        return

    # Length mismatch
    if selected_length != "all" and len(word) != int(selected_length):
        await message.delete()
        return

    # Must start with last letter of previous word
    if last_word and word[0] != last_word[-1]:
        await message.delete()
        return

    # Duplicate word
    if word in used_words_set:
        await message.delete()
        return

    # Dictionary check
    async def is_valid_word(word):
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status == 200

    if not await is_valid_word(word):
        await message.delete()
        return

    # ✅ Word is valid — record and react
    await message.add_reaction("✅")

    word_entry = {
        "user_id": message.author.id,
        "username": message.author.display_name,
        "word": word,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    words_used.append(word_entry)

    user_id = str(message.author.id)
    if user_id not in participants:
        participants[user_id] = {
            "word_count": 0,
            "letter_score": 0
        }

    participants[user_id]["word_count"] += 1
    participants[user_id]["letter_score"] += len(word)

    game["words_used"] = words_used
    game["participants"] = participants
    game["last_word"] = word
    data[guild_id] = game
    save_json(LAST_LETTER_GAME_FILE, data)

@bot.command(name="def")
async def define_word(ctx, *, word: str):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await ctx.send(f"❌ Error: Dictionary API returned status code {response.status}")
                    return
                data = await response.json()

        if not data or not isinstance(data[0], dict) or "meanings" not in data[0]:
            await ctx.send(f"❌ No definitions found for `{word}`.")
            return

        entry = data[0]
        meanings = entry.get("meanings", [])
        definitions = []
        for meaning in meanings:
            part_of_speech = meaning.get("partOfSpeech", "n/a")
            for d in meaning.get("definitions", []):
                definition = d.get("definition")
                if definition:
                    definitions.append(f"**{part_of_speech}** — {definition}")
                if len(definitions) >= 3:
                    break
            if len(definitions) >= 3:
                break

        if not definitions:
            await ctx.send(f"❌ No usable definitions found for `{word}`.")
            return

        embed = discord.Embed(
            title=f"📘 Definition of `{word}`",
            description="\n\n".join(definitions),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ Error while fetching definition: {e}")


@bot.command()
async def cyb(ctx):
    embed1 = discord.Embed(
        title="Last fm Section",
        description="All available Last fm commands:",
        color=discord.Color.blue()
    )
    embed1.add_field(
        name="!setlastfm <lastfm username>",
        value="Link your Last.fm account to your Discord ID.",
        inline=False
    )
    embed1.add_field(
        name="!removelastfm",
        value="Remove your linked Last.fm account from the bot.",
        inline=False
    )
    embed1.add_field(
        name="!np [lastfm username/@mention]",
        value="Show your (or someone else’s) now-playing track from Last.fm.",
        inline=False
    )
    embed1.add_field(
        name="!nps",
        value="List now-playing tracks for everyone in the server who has linked a Last.fm account to this bot.",
        inline=False
    )
    embed1.add_field(
        name="!cyb",
        value="Show this message.",
        inline=False
    )
    embed1.add_field(
        name="!lyr [lastfm username/@mention/artist - song (must use the dash)]",
        value="Get lyrics for the song you're (or someone else is) listening to on Last.fm if possible.",
        inline=False
    )
    embed1.add_field(
        name="!alllastfm",
        value="List all server members who have registered a Last.fm username.",
        inline=False
    )

    embed2 = discord.Embed(
        title="Last Letter Section",
        description="All available last letter commands:",
        color=discord.Color.purple()
    )
    embed2.add_field(
        name="!setchannel",
        value="Set the current channel as the word tracking channel.",
        inline=False
    )
    embed2.add_field(
        name="!scanchannel",
        value="Scan the channel’s history, Only use !scanchannel when setting up the channel, use !uc after that.",
        inline=False
    )
    embed2.add_field(
        name="!uc",
        value="Update the last letter channel stats.",
        inline=False
    )
    embed2.add_field(
        name="!clearchannel",
        value="Clear all word stats for this channel.",
        inline=False
    )
    embed2.add_field(
        name="!totalwords",
        value="Show the total word count.",
        inline=False
    )
    embed2.add_field(
        name="!az [7d/30d/90d/all]",
        value="Show A-Z letter usage stats.",
        inline=False
    )
    embed2.add_field(
        name="!lpw [7d/30d/90d/all]",
        value="List users by their average letters per word.",
        inline=False
    )
    embed2.add_field(
        name="!longestwords [7d/30d/90d/all]",
        value="Display the longest words with user info.",
        inline=False
    )
    embed2.add_field(
        name="!mostwords [7d/30d/90d/all]",
        value="Show the top users by total words sent.",
        inline=False
    )
    embed2.add_field(
        name="!glb [7d/30d/90d/all]",
        value="Global Server Leaderboard.",
        inline=False
    )
    embed2.add_field(
        name="!glbu [7d/30d/90d/all]",
        value="Global User Leaderboard.",
        inline=False
    )
    embed2.add_field(
        name="!def <word>",
        value="Get a dictionary definition for the word.",
        inline=False
    )
    embed2.add_field(
        name="!lastletter",
        value="Show the current status of the Last Letter game.",
        inline=False
    )
    embed2.add_field(
        name="!startlastletter",
        value="Start the Last Letter game.",
        inline=False
    )
    embed2.add_field(
        name="!changelength",
        value="Change the length if you want",
        inline=False
    )
    embed2.add_field(
        name="!endlastletter",
        value="End the Last Letter game and show final stats",
        inline=False
    )

    view = HelpMenuView([embed1, embed2])
    await ctx.send(embed=embed1, view=view)


@bot.tree.command(name="serverinfo", description="Shows basic server information.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title="📊 Server Information", color=discord.Color.blurple())
    embed.add_field(name="Server Name", value=guild.name, inline=False)
    embed.add_field(name="Server ID", value=guild.id, inline=False)
    embed.add_field(name="Member Count", value=guild.member_count, inline=False)

    await interaction.response.send_message(embed=embed)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
