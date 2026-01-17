import logging
import asyncio
import os
import datetime
from pyrogram import Client, enums
from pyrogram.types import Message as PyMessage
from aiogram.types import FSInputFile
import config
import database
from loader import bot

class UserBotManager:
    def __init__(self):
        self.clients = {} # user_id -> Client
        self.is_running = False

    async def start(self):
        """Load all sessions from DB and start them"""
        if self.is_running: return
        
        sessions = database.get_all_sessions()
        logging.info(f"UserBotManager: Found {len(sessions)} sessions.")
        
        for row in sessions:
            if len(row) == 2:
                user_id, session_string = row
            else:
                 user_id = row[0]
                 session_string = row[1] if len(row) > 1 else None

            if session_string:
                await self.start_client(user_id, session_string)
        
        self.is_running = True

    async def start_client(self, user_id: int, session_string: str):
        if user_id in self.clients:
            return
        
        try:
            client = Client(
                name=f"session_{user_id}",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=session_string,
                in_memory=True
            )
            
            self.register_handlers(client, user_id)
            
            await client.start()
            self.clients[user_id] = client
            logging.info(f"UserBot for user {user_id} started.")
            
            # Send alive message to self (silent check)
            try:
                # await client.send_message("me", "🤖 Антигравити бот активен и следит за сообщениями.")
                pass
            except: pass
            
        except Exception as e:
            logging.error(f"Failed to start UserBot for {user_id}: {e}")

    async def stop_client(self, user_id: int):
        client = self.clients.pop(user_id, None)
        if client:
            try:
                await client.stop()
            except: pass

    def register_handlers(self, client: Client, user_id: int):
        
        @client.on_message()
        async def py_on_message(c, message: PyMessage):
            try:
                # 1. Self & Bot Ignore
                if message.from_user and message.from_user.is_self: return
                if client.me and message.from_user and message.from_user.id == client.me.id: return
                
                try:
                    bot_id = int(config.BOT_TOKEN.split(':')[0])
                    if message.chat.id == bot_id or (message.from_user and message.from_user.id == bot_id):
                        return
                except: pass

                # 2. Filter: Only Private Chats
                if message.chat.type != enums.ChatType.PRIVATE:
                    return 

                # 3. Data Extraction Helpers
                def get_fid(obj): return getattr(obj, "file_id", None)
                
                # Pre-calculate flags
                is_protected = getattr(message, "protected_content", False) or getattr(message, "has_protected_content", False)
                has_ttl = False
                if hasattr(message, 'ttl_seconds') and message.ttl_seconds: has_ttl = True
                
                # Deep attribute check for TTL
                if not has_ttl:
                    for attr in ['photo', 'video', 'voice', 'video_note', 'audio', 'document']:
                        obj = getattr(message, attr, None)
                        if obj and hasattr(obj, 'ttl_seconds') and obj.ttl_seconds:
                            has_ttl = True; break

                # Extract basic info
                s_id = message.from_user.id if message.from_user else 0
                s_name = message.from_user.first_name if message.from_user else "Unknown"
                s_username = message.from_user.username if message.from_user and message.from_user.username else None
                
                media_type = None; file_id = None; content = message.text or message.caption or ""
                
                if message.photo: media_type="photo"; file_id=get_fid(message.photo); content=content or "[Фотография]"
                elif message.video: media_type="video"; file_id=get_fid(message.video); content=content or "[Видео]"
                elif message.video_note: media_type="video_note"; file_id=get_fid(message.video_note); content=content or "[Видеокружок]"
                elif message.voice: media_type="voice"; file_id=get_fid(message.voice); content=content or "[Голосовое]"
                elif message.audio: media_type="audio"; file_id=get_fid(message.audio); content=content or "[Аудио]"
                elif message.document: media_type="document"; file_id=get_fid(message.document); content=content or "[Файл]"
                elif message.sticker: media_type="sticker"; file_id=get_fid(message.sticker); content=content or "[Стикер]"
                elif message.animation: media_type="animation"; file_id=get_fid(message.animation); content=content or "[GIF]"
                
                # Fallback for empty media types
                if not media_type and getattr(message, "media", None):
                   content = f"[Медиа: {message.media}]"
                
                logging.info(f"📩 Private Message from {s_id}: Type={media_type}")

                # --- 1. PRIORITY CACHING (Fixes 'Deleted Messages Not Working') ---
                # We cache BEFORE doing any dangerous download operations
                try:
                    database.cache_message(
                        message.id, message.chat.id, user_id, s_id, 
                        content, s_name, media_type, file_id, s_username, 
                        message.chat.title or "Личный чат"
                    )
                except Exception as db_e:
                    logging.error(f"DB Cache Error: {db_e}")

                # --- 2. ULTRA DEEP SEARCH (Raw API & Keywords) ---
                if not has_ttl and not is_protected:
                    # A) Direct Raw Check (The most reliable for TTL)
                    try:
                        if hasattr(message, "raw"):
                             # In raw TLOjbects, media often has 'ttl_seconds'
                             raw_media = getattr(message.raw, "media", None)
                             if raw_media:
                                if hasattr(raw_media, "ttl_seconds") and raw_media.ttl_seconds:
                                     has_ttl = True
                                     logging.info(f"🕵️ Found TTL in RAW media object!")
                    except: pass

                    # B) Keyword Dump Check (Backup)
                    if not has_ttl:
                         # Dump to string to find hidden fields
                        try:
                            debug_dump = str(message)
                            # Expanded keywords list
                            keywords = ["ttl_period", "view_once", "expire", "ttl_seconds", "destroy", "ttl"]
                            if any(k in debug_dump for k in keywords):
                                has_ttl = True
                                is_protected = True
                                logging.info("🕵️ Deep Search found hidden secret keyword!")
                                if not media_type:
                                    if "VIDEO_NOTE" in debug_dump: media_type = "video_note"
                                    elif "VOICE" in debug_dump: media_type = "voice"
                        except: pass
            
                if is_protected or has_ttl:
                    logging.info(f"🔒 Secret Media Detected! Attempting download...")
                    
                    content_secret = f"[🔐 Секретное медиа ({media_type or 'Файл'})] {content} (Сгорающее)"
                    
                    # Attempt Download with Safe Wrapper
                    file_path = None
                    try:
                        # Priority 1: In-Memory (Best for ViewOnce)
                        try:
                           file_bytes = await client.download_media(message, in_memory=True)
                           if file_bytes:
                               ts = int(datetime.datetime.now().timestamp())
                               ext = ".bin"
                               if media_type == "voice": ext = ".ogg"
                               elif media_type == "video_note": ext = ".mp4"
                               elif media_type == "photo": ext = ".jpg"
                               elif media_type == "video": ext = ".mp4"
                               
                               fname = f"downloads/secret_{ts}{ext}"
                               manual_path = os.path.abspath(fname)
                               os.makedirs(os.path.dirname(manual_path), exist_ok=True)
                               
                               with open(manual_path, "wb") as f:
                                   if hasattr(file_bytes, "getbuffer"): f.write(file_bytes.getbuffer())
                                   elif hasattr(file_bytes, "read"): f.write(file_bytes.read())
                                   else: f.write(file_bytes)
                               file_path = manual_path
                        except Exception as ram_e:
                           logging.warning(f"RAM download failed: {ram_e}")
                           # Priority 2: Standard Download
                           file_path = await message.download()

                    except Exception as dl_e:
                        logging.error(f"Download failed: {dl_e}")

                    if file_path:
                        user_tag = f"@{s_username}" if s_username else s_name
                        caption = f"🔐 Секретное медиа от {user_tag}\n📁 Чат: {message.chat.title or 'Личный'}"
                        try:
                            inp = FSInputFile(file_path)
                            sent_msg = None
                            is_voice = (media_type == "voice") or str(file_path).endswith(".ogg")
                            is_video_note = (media_type == "video_note") or str(file_path).endswith(".mp4") and "video_note" in str(file_path)
                            
                            if is_voice: sent_msg = await bot.send_voice(user_id, inp, caption=caption)
                            elif is_video_note: sent_msg = await bot.send_video_note(user_id, inp); await bot.send_message(user_id, caption)
                            elif media_type == "photo": sent_msg = await bot.send_photo(user_id, inp, caption=caption)
                            elif media_type == "video": sent_msg = await bot.send_video(user_id, inp, caption=caption)
                            else: sent_msg = await bot.send_document(user_id, inp, caption=caption)
                        except Exception as send_e:
                             try: await client.send_document("me", file_path, caption=caption + " (Saved to UserBot)")
                             except: pass

                        if os.path.exists(file_path): os.remove(file_path)
                    else:
                        try: await bot.send_message(user_id, f"👀 Замечено секретное медиа ({media_type}), но Telegram не дал его скачать.")
                        except: pass

            except Exception as global_e:
                logging.error(f"CRITICAL ERROR in py_on_message: {global_e}", exc_info=True)


        @client.on_edited_message()
        async def py_on_edit(c, message: PyMessage):
            try:
                if message.from_user and message.from_user.is_self: return
                if message.chat.type != enums.ChatType.PRIVATE: return

                new_text = message.text or message.caption or ""
                if not new_text: new_text = "[Медиа]"
                
                old_data = database.get_cached_message_content(message.id, message.chat.id)
                if old_data:
                    old_text = old_data[0] if old_data else ""
                    
                    if old_text and old_text != new_text:
                         s_name = message.from_user.first_name if message.from_user else "Unknown"
                         alert = (f"✏️ Сообщение изменено!\n👤 {s_name}\n"
                                  f"📜 Было: {old_text}\n🆕 Стало: {new_text}")
                         try: await bot.send_message(user_id, alert)
                         except: pass
                
                # Update cache
                # We need sender info again
                s_name = message.from_user.first_name if message.from_user else "Unknown"
                s_id = message.from_user.id if message.from_user else 0
                database.cache_message(
                    message.id, message.chat.id, user_id, s_id, 
                    new_text, s_name, None, None, message.from_user.username, 
                    "Личный чат"
                )
            except Exception as e:
                logging.error(f"Edit Handler Error: {e}")

    async def check_deleted_messages(self):
        """Periodically check if cached messages still exist"""
        try:
            for user_id, client in self.clients.items():
                if not client.is_connected: continue
                
                cached_msgs = database.get_messages_for_check(user_id)
                if not cached_msgs: continue
                
                # Get exclusions
                try:
                     excluded = [r[0] for r in database.get_excluded_chats(user_id)]
                except: excluded = []
                
                chats = {}
                for row in cached_msgs:
                    mid = row[0]; cid = row[1]; sid = row[2]; content = row[3]
                    sname = row[4]; mtype = row[5]; fid = row[6]; s_username = row[7]
                    
                    if cid in excluded: continue
                    
                    if cid not in chats: chats[cid] = {}
                    chats[cid][mid] = (content, sname, mtype, fid, s_username)
                
                for chat_id, msgs in chats.items():
                    msg_ids = list(msgs.keys())
                    if not msg_ids: continue
                    
                    try:
                        current = await client.get_messages(chat_id, msg_ids)
                        if not isinstance(current, list): current = [current]
                        
                        # Process 
                        for i, msg_obj in enumerate(current):
                            orig_id = msg_ids[i]
                            # Check deletion
                            is_deleted = False
                            if msg_obj is None or (hasattr(msg_obj, 'empty') and msg_obj.empty):
                                is_deleted = True
                                
                            if is_deleted:
                                content, sname, mtype, fid, s_username = msgs[orig_id]
                                tag = f"@{s_username}" if s_username else ""
                                alert = f"🗑 Удалено сообщение!\n👤 {sname} {tag}\n💬 {content}"
                                
                                # Restore media
                                if mtype and fid:
                                    try:
                                        path = await client.download_media(fid)
                                        if path:
                                            inp = FSInputFile(path)
                                            cap = f"🗑 Восстановленное медиа от {sname}"
                                            try:
                                                if mtype=='photo': await bot.send_photo(user_id, inp, caption=cap)
                                                elif mtype=='video': await bot.send_video(user_id, inp, caption=cap)
                                                elif mtype=='voice': await bot.send_voice(user_id, inp, caption=cap)
                                                else: await bot.send_document(user_id, inp, caption=cap)
                                                alert += "\n💾 Медиа восстановлено."
                                            except: alert += "\n❌ Ошибка отправки медиа."
                                            if os.path.exists(path): os.remove(path)
                                    except: pass # alert += "\n❌ Не удалось скачать."
                                
                                await bot.send_message(user_id, alert)
                                database.delete_cached_message(orig_id, chat_id)
                                
                    except Exception as e:
                        # logging.error(f"Check chat {chat_id} failed: {e}")
                        pass

        except Exception as e:
            logging.error(f"Check deleted loop error: {e}")

ub_manager = UserBotManager()
