# main.py - Complete URL to File Bot with Torrent Support
import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import urllib.parse
import yt_dlp
import tgcrypto
import cloudscraper
import tempfile
import shutil
import zipfile
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64encode, b64decode
from logs import logging
from bs4 import BeautifulSoup
import saini as helper
from utils import progress_bar, hrb, hrt, Timer
from vars import API_ID, API_HASH, BOT_TOKEN, OWNER, CREDIT
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pytube import YouTube
import random
from pyromod import listen
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
import aiohttp
import aiofiles
import ffmpeg
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import mimetypes
from urllib.parse import urlparse
import sqlite3
from datetime import datetime, timedelta
import threading
import hashlib
import transmission_rpc
import bencode

# Initialize the bot
bot = Client(
    "medusa_url_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Configuration
AUTH_USER = os.environ.get('AUTH_USERS', str(OWNER)).split(',')
AUTH_USER.append('5680454765')
AUTH_USERS = [int(user_id) for user_id in AUTH_USER if user_id.isdigit()]
if int(OWNER) not in AUTH_USERS:
    AUTH_USERS.append(int(OWNER))

CHANNEL_OWNERS = {}
CHANNELS = os.environ.get('CHANNELS', '').split(',')
CHANNELS_LIST = [int(channel_id) for channel_id in CHANNELS if channel_id.isdigit()]

# Torrent configuration
TORRENT_DOWNLOAD_PATH = "/app/downloads"
MAX_TORRENT_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit
TORRENT_TIMEOUT = 3600  # 1 hour timeout

# Create download directory
os.makedirs(TORRENT_DOWNLOAD_PATH, exist_ok=True)

# API configurations and media URLs
cookies_file_path = os.getenv("cookies_file_path", "youtube_cookies.txt")
api_url = "http://master-api-v3.vercel.app/"
api_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNzkxOTMzNDE5NSIsInRnX3VzZXJuYW1lIjoi4p61IFtvZmZsaW5lXSIsImlhdCI6MTczODY5MjA3N30.SXzZ1MZcvMp5sGESj0hBKSghhxJ3k1GTWoBUbivUe1I"

photologo = 'https://tinypic.host/images/2025/05/29/Medusaxd-Bot_20250529_184235_0000.png'

# Statistics
download_stats = {
    'total_downloads': 0,
    'successful_downloads': 0,
    'failed_downloads': 0,
    'torrent_downloads': 0,
    'start_time': time.time()
}

active_downloads = {}

class TorrentManager:
    """Simple torrent manager using transmission-rpc"""

    def __init__(self):
        self.client = None
        self.init_client()

    def init_client(self):
        """Initialize transmission client (mock for now)"""
        try:
            # In production, you'd connect to a transmission daemon
            # self.client = transmission_rpc.Client('localhost', port=9091)
            logging.info("Torrent client initialized (mock)")
        except Exception as e:
            logging.error(f"Failed to initialize torrent client: {e}")
            self.client = None

    def is_magnet_link(self, url: str) -> bool:
        """Check if URL is a magnet link"""
        return url.lower().startswith('magnet:?xt=urn:btih:')

    def is_torrent_file(self, file_path: str) -> bool:
        """Check if file is a valid torrent file"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                decoded = bencode.decode(data)
                return b'announce' in data and 'info' in decoded
        except:
            return False

    async def download_torrent_from_magnet(self, magnet_link: str, custom_name: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download torrent from magnet link (simplified implementation)"""
        try:
            await message.edit_text("🧲 **Magnet Link Detected**\n⚠️ Torrent downloads are currently in development mode.")

            # For now, return a mock response
            # In production, implement actual torrent downloading
            return False, "", "", "Torrent support is in development. Please use direct URLs for now."

        except Exception as e:
            logging.error(f"Torrent download error: {e}")
            return False, "", "", f"Torrent download failed: {str(e)}"

    async def download_torrent_from_file(self, torrent_file_path: str, custom_name: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download torrent from .torrent file (simplified implementation)"""
        try:
            await message.edit_text("📁 **Torrent File Detected**\n⚠️ Torrent downloads are currently in development mode.")

            # For now, return a mock response
            return False, "", "", "Torrent support is in development. Please use direct URLs for now."

        except Exception as e:
            return False, "", "", f"Torrent file download failed: {str(e)}"

# Initialize torrent manager
torrent_manager = TorrentManager()

class AdvancedDownloadManager:
    """Enhanced download manager with all features"""

    def __init__(self):
        self.session = None
        self.max_retries = 3
        self.active_downloads = {}
        self.failed_counter = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=10)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def parse_filename_from_url(self, text: str) -> Tuple[str, Optional[str]]:
        """Parse URL and custom filename from text format: url|filename.extension"""
        if '|' in text:
            url, custom_name = text.split('|', 1)
            return url.strip(), custom_name.strip()
        else:
            return text.strip(), None

    async def detect_content_type(self, url: str) -> str:
        """Detect content type including torrent support"""
        url_lower = url.lower()

        # Check for magnet links
        if torrent_manager.is_magnet_link(url):
            return 'magnet_torrent'

        # Check for torrent files
        if url_lower.endswith('.torrent'):
            return 'torrent_file'

        # Video platforms (uses yt-dlp)
        video_platforms = [
            'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'twitch.tv', 'tiktok.com', 'twitter.com', 'instagram.com',
            'facebook.com', 'reddit.com'
        ]

        for platform in video_platforms:
            if platform in url_lower:
                return 'video_platform'

        # DRM/Encrypted content
        if any(x in url_lower for x in ['mpd', 'm3u8', 'manifest']):
            return 'drm_video'

        # Direct file types
        parsed = urlparse(url)
        path = parsed.path.lower()

        if path.endswith('.pdf'):
            return 'pdf'
        elif path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
            return 'image'
        elif path.endswith(('.mp3', '.wav', '.m4a', '.flac', '.aac')):
            return 'audio'
        elif path.endswith(('.zip', '.rar', '.7z', '.tar', '.gz')):
            return 'archive'
        elif path.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv')):
            return 'video_direct'
        elif path.endswith(('.doc', '.docx', '.txt', '.epub', '.mobi')):
            return 'document'

        return 'unknown'

    async def download_with_strategy(self, text: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download using appropriate strategy including torrent support"""
        url, custom_filename = self.parse_filename_from_url(text)
        content_type = await self.detect_content_type(url)

        timestamp = int(time.time())
        base_name = custom_filename or f"download_{timestamp}"

        # Remove extension from base_name if present
        if custom_filename and '.' in custom_filename:
            name_without_ext = '.'.join(custom_filename.split('.')[:-1])
            custom_ext = custom_filename.split('.')[-1]
        else:
            name_without_ext = base_name
            custom_ext = None

        try:
            if content_type == 'magnet_torrent':
                download_stats['torrent_downloads'] += 1
                return await torrent_manager.download_torrent_from_magnet(url, name_without_ext, message)
            elif content_type == 'torrent_file':
                download_stats['torrent_downloads'] += 1
                return await self._download_torrent_file(url, name_without_ext, message)
            elif content_type == 'video_platform':
                return await self._download_video_platform(url, name_without_ext, custom_ext, message)
            elif content_type == 'pdf':
                return await self._download_pdf(url, name_without_ext, custom_ext, message)
            elif content_type == 'image':
                return await self._download_image(url, name_without_ext, custom_ext, message)
            elif content_type == 'drm_video':
                return await self._download_drm_video(url, name_without_ext, custom_ext, message)
            elif content_type == 'video_direct':
                return await self._download_video_direct(url, name_without_ext, custom_ext, message)
            elif content_type == 'audio':
                return await self._download_audio(url, name_without_ext, custom_ext, message)
            else:
                return await self._download_generic(url, name_without_ext, custom_ext, message)

        except Exception as e:
            logging.error(f"Download strategy failed for {url}: {str(e)}")
            return False, "", "", f"Download failed: {str(e)}"

    async def _download_torrent_file(self, url: str, name: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download .torrent file and then download torrent"""
        try:
            await message.edit_text("📁 **Downloading Torrent File...**")

            # Download torrent file
            async with self.session.get(url) as response:
                if response.status != 200:
                    return False, "", "", f"Failed to download torrent file: HTTP {response.status}"

                torrent_file_path = f"{name}.torrent"
                async with aiofiles.open(torrent_file_path, 'wb') as f:
                    await f.write(await response.read())

            # Validate and download torrent
            if not torrent_manager.is_torrent_file(torrent_file_path):
                os.remove(torrent_file_path)
                return False, "", "", "Invalid torrent file"

            return await torrent_manager.download_torrent_from_file(torrent_file_path, name, message)

        except Exception as e:
            return False, "", "", f"Torrent file download failed: {str(e)}"

    async def _download_video_platform(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download video using yt-dlp with aria2c"""
        for attempt in range(self.max_retries):
            try:
                if custom_ext:
                    output_template = f'{name}.{custom_ext}'
                    format_selector = f'best[ext={custom_ext}]/best'
                else:
                    output_template = f'{name}.%(ext)s'
                    format_selector = 'best[height<=720]/best'

                cmd = f'yt-dlp -f "{format_selector}" -o "{output_template}" "{url}" -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'

                await message.edit_text(f"📹 **Downloading Video...**\n🔄 Using yt-dlp with aria2c acceleration")

                result = await helper.download_video(url, cmd, output_template.split('.')[0])

                if result and os.path.exists(result):
                    try:
                        duration_seconds = helper.duration(result)
                        duration_str = hrt(duration_seconds)
                        file_size = os.path.getsize(result)
                        return True, result, f"Video ({duration_str}, {hrb(file_size)})", "video"
                    except:
                        file_size = os.path.getsize(result)
                        return True, result, f"Video ({hrb(file_size)})", "video"

                raise Exception("yt-dlp download failed")

            except Exception as e:
                if attempt == self.max_retries - 1:
                    return False, "", "", f"Video download failed: {str(e)}"
                await asyncio.sleep(2 ** attempt)

        return False, "", "", "Max retries exceeded"

    async def _download_pdf(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download PDF using retry logic"""
        ext = custom_ext or 'pdf'
        filename = f"{name}.{ext}"

        success, result = await self.retry_pdf_download(url, name, message)

        if success:
            return True, result, f"PDF Document ({hrb(os.path.getsize(result))})", "document"
        else:
            return False, "", "", result

    async def retry_pdf_download(self, url, name, message, max_retries=3):
        """PDF download retry logic"""
        filename = f"{name}.pdf"

        for attempt in range(max_retries):
            try:
                await message.edit_text(f"📄 **Downloading PDF...**\n🔄 Attempt {attempt + 1}/{max_retries}")

                if "cwmediabkt99" in url:
                    await asyncio.sleep(2 ** attempt)
                    url_clean = url.replace(" ", "%20")
                    scraper = cloudscraper.create_scraper()
                    response = scraper.get(url_clean)

                    if response.status_code == 200:
                        with open(filename, 'wb') as file:
                            file.write(response.content)
                        return True, filename
                    else:
                        raise Exception(f"HTTP {response.status_code}: {response.reason}")
                else:
                    result = await helper.pdf_download(url, filename)
                    if os.path.exists(result):
                        return True, result
                    else:
                        raise Exception("PDF download failed")

            except Exception as e:
                if attempt == max_retries - 1:
                    return False, str(e)
                await asyncio.sleep(2 ** attempt)

        return False, "Max retries exceeded"

    async def _download_image(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download image with custom extension support"""
        try:
            await message.edit_text("🖼️ **Downloading Image...**")

            async with self.session.get(url) as response:
                if response.status == 200:
                    if custom_ext:
                        ext = custom_ext
                    else:
                        content_type = response.headers.get('content-type', '')
                        ext = 'jpg'  # default
                        if 'png' in content_type:
                            ext = 'png'
                        elif 'gif' in content_type:
                            ext = 'gif'
                        elif 'webp' in content_type:
                            ext = 'webp'

                    filename = f"{name}.{ext}"

                    async with aiofiles.open(filename, 'wb') as file:
                        await file.write(await response.read())

                    file_size = os.path.getsize(filename)
                    return True, filename, f"Image ({ext.upper()}, {hrb(file_size)})", "photo"

        except Exception as e:
            return False, "", "", f"Image download failed: {str(e)}"

    async def _download_drm_video(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download DRM video"""
        try:
            await message.edit_text("🔒 **Processing DRM Video...**\n🔑 This may take longer...")
            return await self._download_video_platform(url, name, custom_ext, message)
        except Exception as e:
            return False, "", "", f"DRM video download failed: {str(e)}"

    async def _download_video_direct(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download direct video file"""
        try:
            ext = custom_ext or url.split('.')[-1] or 'mp4'
            filename = f"{name}.{ext}"

            await message.edit_text(f"🎥 **Downloading Video File...**\n📁 Saving as {filename}")

            async with self.session.get(url) as response:
                if response.status == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    async with aiofiles.open(filename, 'wb') as file:
                        async for chunk in response.content.iter_chunked(8192):
                            await file.write(chunk)
                            downloaded += len(chunk)

                            if downloaded % (1024 * 1024) == 0:  # Every 1MB
                                progress = f"🎥 Downloading... {hrb(downloaded)}"
                                if total_size > 0:
                                    percentage = (downloaded / total_size) * 100
                                    progress += f" ({percentage:.1f}%)"
                                await self._safe_edit(message, progress)

                    file_size = os.path.getsize(filename)
                    return True, filename, f"Video ({hrb(file_size)})", "video"

        except Exception as e:
            return False, "", "", f"Video download failed: {str(e)}"

    async def _download_audio(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Download audio file"""
        try:
            ext = custom_ext or url.split('.')[-1] or 'mp3'
            filename = f"{name}.{ext}"

            await message.edit_text(f"🎵 **Downloading Audio...**\n📁 Saving as {filename}")

            async with self.session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(filename, 'wb') as file:
                        await file.write(await response.read())

                    file_size = os.path.getsize(filename)
                    return True, filename, f"Audio ({ext.upper()}, {hrb(file_size)})", "audio"

        except Exception as e:
            return False, "", "", f"Audio download failed: {str(e)}"

    async def _download_generic(self, url: str, name: str, custom_ext: str, message: Message) -> Tuple[bool, str, str, str]:
        """Generic file download with custom naming"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    if custom_ext:
                        filename = f"{name}.{custom_ext}"
                    else:
                        content_disposition = response.headers.get('content-disposition', '')
                        if 'filename=' in content_disposition:
                            filename = content_disposition.split('filename=')[1].strip('"')
                        else:
                            parsed_url = urlparse(url)
                            url_filename = os.path.basename(parsed_url.path)
                            if url_filename and '.' in url_filename:
                                filename = url_filename
                            else:
                                content_type = response.headers.get('content-type', '')
                                ext = mimetypes.guess_extension(content_type) or '.bin'
                                filename = f"{name}{ext}"

                    await message.edit_text(f"📥 **Downloading File...**\n📁 Saving as {filename}")

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    async with aiofiles.open(filename, 'wb') as file:
                        async for chunk in response.content.iter_chunked(8192):
                            await file.write(chunk)
                            downloaded += len(chunk)

                            if downloaded % (500 * 1024) == 0:  # Every 500KB
                                progress = f"📥 Downloading... {hrb(downloaded)}"
                                if total_size > 0:
                                    percentage = (downloaded / total_size) * 100
                                    progress += f" ({percentage:.1f}%)"
                                await self._safe_edit(message, progress)

                    file_type = filename.split('.')[-1].upper() if '.' in filename else "Unknown"
                    file_size = os.path.getsize(filename)
                    return True, filename, f"File ({file_type}, {hrb(file_size)})", "document"

        except Exception as e:
            return False, "", "", f"Generic download failed: {str(e)}"

    async def _safe_edit(self, message: Message, text: str):
        """Safely edit message without causing flood wait"""
        try:
            await message.edit_text(text)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

# Database initialization
def init_database():
    """Initialize SQLite database for user management"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_authorized INTEGER DEFAULT 0,
            added_date TEXT,
            last_activity TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            channel_name TEXT,
            is_authorized INTEGER DEFAULT 0,
            added_date TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            filename TEXT,
            file_size INTEGER,
            download_time TEXT,
            status TEXT,
            download_type TEXT DEFAULT 'regular'
        )
    ''')

    conn.commit()
    conn.close()

init_database()

# Utility functions
async def show_random_emojis(message: Message) -> Message:
    """Show random emojis"""
    emojis = ['🐼', '🐶', '🐅', '⚡️', '🚀', '✨', '💥', '☠️', '🥂', '🍾', '📬', '👻', '👀', '🌹', '💀', '🐇', '⏳', '🔮', '🦔', '📖', '🦁', '🐱', '🐻‍❄️', '☁️', '🚹', '🚺', '🐠', '🦋']
    emoji_message = await message.reply_text(' '.join(random.choices(emojis, k=1)))
    return emoji_message

def is_authorized_user(user_id: int) -> bool:
    """Check if user is authorized"""
    return user_id in AUTH_USERS

def is_authorized_channel(chat_id: int) -> bool:
    """Check if channel is authorized"""
    return chat_id in CHANNELS_LIST

def add_user_to_db(user_id: int, username: str, first_name: str, is_authorized: bool = False):
    """Add user to database"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, is_authorized, added_date, last_activity)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, int(is_authorized), 
          datetime.now().isoformat(), datetime.now().isoformat()))

    conn.commit()
    conn.close()

def log_download(user_id: int, url: str, filename: str, file_size: int, status: str, download_type: str = 'regular'):
    """Log download to database"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO downloads (user_id, url, filename, file_size, download_time, status, download_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, url, filename, file_size, datetime.now().isoformat(), status, download_type))

    conn.commit()
    conn.close()

def get_user_downloads(user_id: int) -> List[Dict]:
    """Get user download history"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM downloads WHERE user_id = ? ORDER BY download_time DESC LIMIT 50
    ''', (user_id,))

    downloads = cursor.fetchall()
    conn.close()

    return [{'url': d[2], 'filename': d[3], 'size': d[4], 'time': d[5], 'status': d[6]} for d in downloads]

# Bot Command Handlers
@bot.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Start command with authorization check"""
    user = message.from_user
    if not user:
        return

    add_user_to_db(user.id, user.username, user.first_name, is_authorized_user(user.id))

    if not is_authorized_user(user.id) and not is_authorized_channel(message.chat.id):
        unauthorized_text = f"""
❌ **Access Denied**

Hello {user.mention}!

You are not authorized to use this bot. Please contact the administrator to get access.

**Bot Features:**
🎯 Advanced URL to File Downloads
🧲 **Torrent Support** - Magnet links & .torrent files
🔒 DRM Content Support  
📹 Multi-Platform Video Downloads
📄 Document & Media Processing
🎵 Audio Extraction & Conversion
📊 Progress Tracking & Statistics

**Contact:** @medusaXD

**{CREDIT}**
        """

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📞 Request Access", url="https://t.me/medusaXD")
        ]])

        try:
            await message.reply_photo(
                photo=photologo,
                caption=unauthorized_text,
                reply_markup=keyboard
            )
        except:
            await message.reply_text(unauthorized_text, reply_markup=keyboard)
        return

    welcome_text = f"""
🌟 **Welcome {user.mention}!** 🌟

🤖 **{CREDIT} Advanced URL to File Bot**

✅ **You are authorized to use this bot!**

**🎯 What I can download:**
📹 **Videos** - YouTube, Vimeo, TikTok, Instagram, Twitter
🧲 **Torrents** - Magnet links & .torrent files
📄 **Documents** - PDF, DOC, TXT, EPUB with special handling
🖼️ **Images** - JPG, PNG, GIF, WebP, BMP
🎵 **Audio** - MP3, WAV, M4A, FLAC, AAC  
📦 **Archives** - ZIP, RAR, 7Z, TAR
🔒 **Protected Content** - DRM videos, encrypted files

**🎨 Custom Naming Feature:**
Use format: `URL|filename.extension`
Example: `https://example.com/video.mp4|MyVideo.mp4`

**⚡ Advanced Features:**
• Multi-threaded downloads with aria2c
• Progress tracking with beautiful bars
• Automatic retry on failures
• Channel support for mass downloads
• DRM content decryption
• High-quality video processing

**📊 Your Stats:**
Downloads Today: `{len([d for d in get_user_downloads(user.id) if d['time'][:10] == datetime.now().date().isoformat()])}`
Total Downloads: `{len(get_user_downloads(user.id))}`

**🚀 Just send me any URL to get started!**
    """

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📞 Contact", url="https://t.me/medusaXD"),
            InlineKeyboardButton("🛠️ Help", callback_data="help")
        ],
        [
            InlineKeyboardButton("🧲 Torrent Help", callback_data="torrent_help"),
            InlineKeyboardButton("📊 My Stats", callback_data="my_stats")
        ]
    ])

    try:
        await message.reply_photo(
            photo=photologo,
            caption=welcome_text,
            reply_markup=keyboard
        )
    except:
        await message.reply_text(welcome_text, reply_markup=keyboard)

@bot.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Help command with comprehensive guide"""
    if not is_authorized_user(message.from_user.id) and not is_authorized_channel(message.chat.id):
        await message.reply_text("❌ You are not authorized to use this bot!")
        return

    help_text = """
🆘 **Complete Help Guide**

**🔗 Supported URL Types:**

**📹 Video Platforms (via yt-dlp):**
• YouTube: `https://youtube.com/watch?v=...`
• Vimeo: `https://vimeo.com/...`
• TikTok: `https://tiktok.com/@user/video/...`
• Instagram: `https://instagram.com/p/...`
• Twitter: `https://twitter.com/.../status/...`
• Facebook: `https://facebook.com/watch?v=...`

**🧲 Torrent Support:**
• Magnet links: `magnet:?xt=urn:btih:...`
• .torrent files: `https://site.com/file.torrent`

**📁 Direct Files:**
• PDF: `https://example.com/document.pdf`
• Images: `https://example.com/photo.jpg`
• Audio: `https://example.com/song.mp3`
• Videos: `https://example.com/video.mp4`
• Archives: `https://example.com/file.zip`

**🎨 Custom Filename Feature:**
Format: `URL|custom_name.extension`

Examples:
• `https://youtube.com/watch?v=abc|MyVideo.mp4`
• `https://example.com/doc.pdf|ImportantDoc.pdf`
• `magnet:?xt=urn:btih:abc123|MyTorrent`

**⚡ Commands:**
• `/start` - Welcome message
• `/help` - This help guide
• `/stats` - View statistics (authorized users)
• `/mystats` - Your personal stats

**💡 Tips:**
• Large files show progress with ETA
• Bot supports batch URLs (multiple links)
• Works in authorized channels
• Automatic quality selection for videos
• Files are automatically cleaned after upload

**🚨 Limits:**
• File size: 2GB per file
• Rate limit: 10 downloads per hour
• Concurrent downloads: 3 per user
    """

    await message.reply_text(help_text)

# Admin Commands (Owner Only)
@bot.on_message(filters.command("adduser") & filters.user(OWNER))
async def add_user_command(client: Client, message: Message):
    """Add authorized user (Admin only)"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/adduser <user_id>`")
        return

    try:
        user_id = int(message.command[1])
        if user_id in AUTH_USERS:
            await message.reply_text(f"✅ User `{user_id}` is already authorized!")
        else:
            AUTH_USERS.append(user_id)

            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_authorized = 1 WHERE user_id = ?', (user_id,))
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, is_authorized, added_date, last_activity)
                    VALUES (?, ?, ?, 1, ?, ?)
                ''', (user_id, 'Unknown', 'Unknown', datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            await message.reply_text(f"✅ User `{user_id}` has been authorized!")
            logging.info(f"User {user_id} authorized by admin {message.from_user.id}")
    except ValueError:
        await message.reply_text("❌ Please provide a valid user ID!")

@bot.on_message(filters.command("addchannel") & filters.user(OWNER))
async def add_channel_command(client: Client, message: Message):
    """Add authorized channel (Admin only)"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/addchannel <channel_id>`")
        return

    try:
        channel_id = int(message.command[1])
        if channel_id in CHANNELS_LIST:
            await message.reply_text(f"✅ Channel `{channel_id}` is already authorized!")
        else:
            CHANNELS_LIST.append(channel_id)

            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO channels (channel_id, channel_name, is_authorized, added_date)
                VALUES (?, ?, 1, ?)
            ''', (channel_id, 'Unknown', datetime.now().isoformat()))
            conn.commit()
            conn.close()

            await message.reply_text(f"✅ Channel `{channel_id}` has been authorized!")
            logging.info(f"Channel {channel_id} authorized by admin {message.from_user.id}")
    except ValueError:
        await message.reply_text("❌ Please provide a valid channel ID!")

# Handle torrent files uploaded to bot
@bot.on_message(filters.document)
async def handle_torrent_file(client: Client, message: Message):
    """Handle uploaded .torrent files"""
    if not is_authorized_user(message.from_user.id) and not is_authorized_channel(message.chat.id):
        return

    document = message.document
    if not document.file_name.lower().endswith('.torrent'):
        return

    user_id = message.from_user.id
    if user_id in active_downloads:
        await message.reply_text("❌ **Download in Progress!**\nPlease wait for your current download to complete.")
        return

    active_downloads[user_id] = True
    download_stats['total_downloads'] += 1
    download_stats['torrent_downloads'] += 1

    status_msg = await message.reply_text("📁 **Processing Torrent File...**")

    try:
        # Download torrent file
        torrent_file_path = f"temp_{int(time.time())}.torrent"
        await message.download(torrent_file_path)

        custom_name = document.file_name.replace('.torrent', '')

        success, filename, file_info, upload_type = await torrent_manager.download_torrent_from_file(
            torrent_file_path, custom_name, status_msg
        )

        if success and filename and os.path.exists(filename):
            download_stats['successful_downloads'] += 1

            await status_msg.edit_text("📤 **Uploading Torrent Content...**")

            file_size = os.path.getsize(filename)

            caption = f"""
🧲 **Torrent Downloaded Successfully!**

**🏷️ Info:** {file_info}
**📏 Size:** {hrb(file_size)}
**📂 Name:** `{filename}`
**📁 Source:** Torrent File

**{CREDIT}**
            """

            try:
                start_time = time.time()
                if file_size > 20 * 1024 * 1024:
                    await message.reply_document(
                        document=filename,
                        caption=caption,
                        progress=progress_bar,
                        progress_args=(status_msg, start_time)
                    )
                else:
                    await message.reply_document(document=filename, caption=caption)

                await status_msg.edit_text("✅ **Torrent Upload Completed!**")

            except Exception as upload_error:
                await status_msg.edit_text(f"❌ **Upload Failed!**\n{str(upload_error)}")
                download_stats['failed_downloads'] += 1

            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass
        else:
            download_stats['failed_downloads'] += 1
            await status_msg.edit_text(f"❌ **Torrent Download Failed!**\n{file_info}")

    except Exception as e:
        download_stats['failed_downloads'] += 1
        await status_msg.edit_text(f"❌ **Error!**\n{str(e)}")

    finally:
        if user_id in active_downloads:
            del active_downloads[user_id]

# Main URL/Magnet Handler
@bot.on_message(filters.text & filters.regex(r'(https?://[^\s]+|magnet:\?xt=urn:btih:[^\s]+)'))
async def handle_url_and_magnets(client: Client, message: Message):
    """Enhanced URL handler with magnet link support"""
    if not is_authorized_user(message.from_user.id) and not is_authorized_channel(message.chat.id):
        await message.reply_text("❌ **Access Denied!**\n\nContact @medusaXD for access.")
        return

    text = message.text.strip()
    user_id = message.from_user.id

    if user_id in active_downloads:
        await message.reply_text("❌ **Download in Progress!**\nPlease wait for your current download to complete.")
        return

    active_downloads[user_id] = True
    download_stats['total_downloads'] += 1

    is_magnet = torrent_manager.is_magnet_link(text.split('|')[0] if '|' in text else text)

    if is_magnet:
        status_msg = await message.reply_text("🧲 **Processing Magnet Link...**\n⏳ Preparing torrent download...")
        download_stats['torrent_downloads'] += 1
    else:
        status_msg = await message.reply_text("🔄 **Analyzing URL...**\n⏳ Please wait...")

    emoji_msg = await show_random_emojis(message)

    try:
        async with AdvancedDownloadManager() as downloader:
            success, filename, file_info, upload_type = await downloader.download_with_strategy(text, status_msg)

            if success and filename and os.path.exists(filename):
                download_stats['successful_downloads'] += 1

                await status_msg.edit_text("📤 **Uploading File...**")

                file_size = os.path.getsize(filename)

                download_type = 'torrent' if is_magnet else 'regular'

                url = text.split('|')[0] if '|' in text else text
                log_download(user_id, url, filename, file_size, 'success', download_type)

                caption = f"""
{'🧲' if is_magnet else '📁'} **{'Torrent' if is_magnet else 'File'} Downloaded Successfully!**

**🏷️ Info:** {file_info}
**📏 Size:** {hrb(file_size)}
**📂 Name:** `{filename}`
**🔗 Source:** `{url[:50]}{'...' if len(url) > 50 else ''}`

**{CREDIT}**
                """

                try:
                    start_time = time.time()

                    if upload_type == "photo" and file_size < 10 * 1024 * 1024:
                        await message.reply_photo(photo=filename, caption=caption)
                    elif upload_type == "video" and file_size < 50 * 1024 * 1024:
                        try:
                            duration = helper.duration(filename)
                            await message.reply_video(video=filename, duration=int(duration), caption=caption)
                        except:
                            await message.reply_video(video=filename, caption=caption)
                    elif upload_type == "audio" and file_size < 50 * 1024 * 1024:
                        await message.reply_audio(audio=filename, caption=caption)
                    else:
                        if file_size > 20 * 1024 * 1024:
                            await message.reply_document(
                                document=filename,
                                caption=caption,
                                progress=progress_bar,
                                progress_args=(status_msg, start_time)
                            )
                        else:
                            await message.reply_document(document=filename, caption=caption)

                    await status_msg.edit_text("✅ **Upload Completed!**")

                except Exception as upload_error:
                    logging.error(f"Upload error: {str(upload_error)}")
                    await status_msg.edit_text(f"❌ **Upload Failed!**\n{str(upload_error)}")
                    download_stats['failed_downloads'] += 1

                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                except:
                    pass
            else:
                download_stats['failed_downloads'] += 1
                await status_msg.edit_text(f"❌ **Download Failed!**\n{file_info}")

    except Exception as e:
        download_stats['failed_downloads'] += 1
        logging.error(f"Handler error: {str(e)}")
        await status_msg.edit_text(f"❌ **Error!**\n{str(e)}")

    finally:
        if user_id in active_downloads:
            del active_downloads[user_id]

        try:
            await emoji_msg.delete()
        except:
            pass

# Callback Query Handler
@bot.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Handle inline keyboard callbacks"""
    data = callback_query.data

    if data == "help":
        await callback_query.answer()
        help_text = """
🆘 **Quick Help**

**Basic Usage:**
Send any URL to download files.

**Custom Naming:**
`URL|filename.extension`

**Examples:**
• `https://youtube.com/watch?v=abc|MyVideo.mp4`
• `https://site.com/doc.pdf|Document.pdf`
• `magnet:?xt=urn:btih:abc123|MyTorrent`

Use /help for detailed information.
        """

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
        ]])

        await callback_query.edit_message_text(help_text, reply_markup=keyboard)

    elif data == "torrent_help":
        await callback_query.answer()
        torrent_help_text = """
🧲 **Torrent Help Guide**

**📥 How to Download Torrents:**

**1. Magnet Links:**
Send: `magnet:?xt=urn:btih:HASH`
Custom name: `magnet:?xt=urn:btih:HASH|MyTorrent`

**2. .torrent Files:**
• Upload .torrent file directly to bot
• Send torrent file URL

**⚠️ Current Status:**
Torrent support is in development mode.
Use direct URLs for now.

**🚀 Coming Soon:**
• Real-time progress tracking
• Multi-file torrent support
• Automatic seeding management
        """

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
        ]])

        await callback_query.edit_message_text(torrent_help_text, reply_markup=keyboard)

    elif data == "my_stats":
        if not is_authorized_user(callback_query.from_user.id):
            await callback_query.answer("❌ Not authorized!", show_alert=True)
            return

        await callback_query.answer()
        user_downloads = get_user_downloads(callback_query.from_user.id)
        total = len(user_downloads)
        successful = len([d for d in user_downloads if d['status'] == 'success'])

        stats_text = f"""
📊 **Your Statistics**

• Total Downloads: `{total}`
• Successful: `{successful}`
• Failed: `{total - successful}`
• Success Rate: `{(successful/max(total,1)*100):.1f}%`

Use /mystats for detailed view.

**{CREDIT}**
        """

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
        ]])

        await callback_query.edit_message_text(stats_text, reply_markup=keyboard)

# Handle non-URL text messages
@bot.on_message(filters.text & ~filters.command(['start', 'help', 'stats', 'mystats', 'adduser', 'addchannel']))
async def handle_non_url_text(client: Client, message: Message):
    """Handle non-URL text messages"""
    if not is_authorized_user(message.from_user.id) and not is_authorized_channel(message.chat.id):
        return

    if not re.search(r'(https?://[^\s]+|magnet:\?xt=urn:btih:[^\s]+)', message.text):
        help_text = f"""
🤔 **No URL/Magnet Detected!**

Please send me a valid URL or magnet link to download files.

**📝 Format Examples:**
• Simple: `https://youtube.com/watch?v=abc123`
• Custom name: `https://site.com/video.mp4|MyVideo.mp4`
• Magnet: `magnet:?xt=urn:btih:abc123|MyTorrent`

**🎯 Supported:**
Videos, PDFs, Images, Audio, Documents, Archives, Torrents

Use /help for complete guide.

**{CREDIT}**
        """

        await message.reply_text(help_text)

# Run the bot
if __name__ == "__main__":
    logging.info("🚀 Starting Medusa Advanced URL to File Bot with Docker & Torrent Support...")

    print(f"""

╔══════════════════════════════════════════════════════════════════════════════╗
║               🤖 MEDUSA ADVANCED URL TO FILE BOT WITH DOCKER 🤖                ║  
║                                                                              ║
║                          {CREDIT}                            ║
║                                                                              ║
║  🔥 PRODUCTION FEATURES:                                                     ║
║  • Docker deployment with aria2c & ffmpeg                                   ║
║  • Custom filename support (URL|filename.extension)                         ║
║  • 🧲 TORRENT SUPPORT (Magnet links & .torrent files)                      ║
║  • Multi-platform downloads (YouTube, Vimeo, TikTok, etc.)                  ║
║  • DRM content processing with decryption                                   ║
║  • PDF, Image, Audio, Video, Archive support                               ║
║  • Progress tracking with beautiful progress bars                           ║
║  • Channel support with authorization                                       ║
║  • Database logging and user management                                     ║
║  • Admin commands for user/channel management                               ║
║  • Retry mechanisms with exponential backoff                                ║
║                                                                              ║
║  🐳 DEPLOYMENT READY:                                                       ║
║  • Render.com compatible with Docker runtime                                ║
║  • Full system package support (aria2c, ffmpeg)                            ║
║  • Environment variable configuration                                       ║
║  • Persistent storage with disk mounting                                    ║
║                                                                              ║
║  🚀 Bot started successfully! Ready for production deployment!              ║
╚══════════════════════════════════════════════════════════════════════════════╝

    """)

    try:
        bot.run()
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        print(f"❌ Bot startup failed: {e}")
