import logging
import asyncio
import os
import datetime
from pyrogram import Client, enums, raw
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
            # USE OFFICIAL ANDROID KEYS FOR MAXIMUM TRUST (REQUIRED FOR VIEW-ONCE)
            client = Client(
                name=f"official_session_{user_id}",
                api_id=6,
                api_hash="eb06d4ab3521ad1297404c23ad8d8e05",
                session_string=session_string,
                in_memory=True,
                device_model="Android",
                system_version="Android 11",
                app_version="8.4.1",
                lang_code="ru"
            )
            logging.info(f"🚀 Starting OFFICIAL Mobile UserBot {user_id}")
            
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
                is_protected = getattr(message, "has_protected_content", False)
                has_ttl = False
                
                # Check for TTL/View-Once at top level
                if hasattr(message, 'ttl_seconds') and message.ttl_seconds: 
                    has_ttl = True
                
                # Deep attribute check for TTL in sub-objects
                for attr in ['photo', 'video', 'voice', 'video_note', 'audio', 'document']:
                    obj = getattr(message, attr, None)
                    if obj:
                        # Check for timer (photo/video/voice/video_note)
                        if getattr(obj, "ttl_seconds", None):
                            has_ttl = True; break
                        # Check for explicit view_once (some API versions)
                        if getattr(obj, "view_once", False):
                            has_ttl = True; break

                # Extract basic info
                s_id = message.from_user.id if message.from_user else 0
                s_name = message.from_user.first_name if message.from_user else "Unknown"
                s_username = message.from_user.username if message.from_user and message.from_user.username else None
                
                media_type = None; file_id = None; content = message.text or message.caption or ""
                
                # Robust Identification using enums (Pyrogram 2.0+)
                m = message.media
                if m == enums.MessageMediaType.PHOTO:
                    media_type = "photo"; file_id = get_fid(message.photo); content = content or "[Фотография]"
                elif m == enums.MessageMediaType.VIDEO:
                    media_type = "video"; file_id = get_fid(message.video); content = content or "[Видео]"
                elif m == enums.MessageMediaType.VIDEO_NOTE:
                    media_type = "video_note"; file_id = get_fid(message.video_note); content = content or "[Видеокружок]"
                elif m == enums.MessageMediaType.VOICE:
                    media_type = "voice"; file_id = get_fid(message.voice); content = content or "[Голосовое]"
                elif m == enums.MessageMediaType.AUDIO:
                    media_type = "audio"; file_id = get_fid(message.audio); content = content or "[Аудио]"
                elif m == enums.MessageMediaType.DOCUMENT:
                    media_type = "document"; file_id = get_fid(message.document); content = content or "[Файл]"
                elif m == enums.MessageMediaType.STICKER:
                    media_type = "sticker"; file_id = get_fid(message.sticker); content = content or "[Стикер]"
                elif m == enums.MessageMediaType.ANIMATION:
                    media_type = "animation"; file_id = get_fid(message.animation); content = content or "[GIF]"
                
                # FALLBACK: If message is non-text and media is still None, try to refetch it
                # OR if it's explicitly Unsupported media (common for view-once on Desktop sessions)
                is_unsupported = False
                if hasattr(message, "media") and str(message.media) == "MessageMediaType.UNSUPPORTED":
                    is_unsupported = True
                    logging.info(f"🕵️ Detected UNSUPPORTED media in message {message.id}. This usually means Desktop session mismatch.")

                if (not message.text and not media_type) or is_unsupported:
                    await asyncio.sleep(1.5) # Wait for media to settle
                    try:
                        message = await client.get_messages(message.chat.id, message.id)
                        
                        # RAW INVOKE for View-Once detection if high-level fails
                        try:
                            raw_res = await client.invoke(
                                raw.functions.messages.GetMessages(id=[raw.types.InputMessageID(id=message.id)])
                            )
                            if hasattr(raw_res, "messages") and raw_res.messages:
                                has_ttl = has_ttl or getattr(raw_res.messages[0].media, "ttl_seconds", 0) > 0
                        except: pass

                        is_protected = getattr(message, "has_protected_content", False)
                        has_ttl = has_ttl or getattr(message, "ttl_seconds", 0) > 0
                        
                        if not media_type:
                            if message.photo: media_type = "photo"; file_id = get_fid(message.photo); content = content or "[Фотография]"
                            elif message.video: media_type = "video"; file_id = get_fid(message.video); content = content or "[Видео]"
                            elif message.voice: media_type = "voice"; file_id = get_fid(message.voice); content = content or "[Голосовое]"
                    except Exception as refetch_e:
                        logging.error(f"Refetch failed: {refetch_e}")

                logging.info(f"📩 Private Message from {s_id}: Type={media_type} Secret={has_ttl or is_protected}")

                logging.info(f"📩 Private Message from {s_id}: Type={media_type}")
                logging.info(f"🕵️ Detection Result: is_protected={is_protected}, has_ttl={has_ttl}")
                
                # Enhanced debug for all non-text messages
                if not message.text:
                    if getattr(message, "media", None):
                        logging.info(f"DEBUG: Media object: {message.media}")
                    try:
                        logging.info(f"FULL MESSAGE DATA: {message}")
                    except: pass

                # --- 1. IMMEDIATE SAVE FOR SECRET MEDIA (Priority) ---
                if is_protected or has_ttl:
                    try:
                        logging.info(f"🔒 Secret media {message.id} detected. Downloading IMMEDIATELY...")
                        os.makedirs("downloads", exist_ok=True)
                        path = await client.download_media(message)
                        if path:
                            file_id = f"LOCAL:{path}" # Update file_id for database
                            logging.info(f"✅ Secret media saved to disk: {path}")
                    except Exception as dl_e:
                        logging.error(f"Immediate download failed: {dl_e}")

                # --- 2. CACHE TO DATABASE ---
                try:
                    database.cache_message(
                        message.id, message.chat.id, user_id, s_id, 
                        content, s_name, media_type, file_id, s_username, 
                        message.chat.title or "Личный чат"
                    )
                except Exception as db_e:
                    logging.error(f"DB Cache Error: {db_e}")

                # --- 3. KEYWORD DUMP CHECK (Fallback) ---
                if not has_ttl:
                    try:
                        dump = str(message).lower()
                        if any(k in dump for k in ["ttl", "view", "once", "expire"]):
                            has_ttl = True
                    except: pass
            
                # --- 4. DOWNLOAD AND FORWARD SECRET MEDIA ---
                if is_protected or has_ttl:
                    logging.info(f"🔒 Secret Media Detected! Attempting download...")
                    
                    content_secret = f"[🔐 Секретное медиа ({media_type or 'Файл'})] {content} (Сгорающее)"
                    
                    # Attempt Download with Safe Wrapper
                    file_path = None
                    # If file_id was already set to LOCAL:path by immediate save, use that
                    if file_id and str(file_id).startswith("LOCAL:"):
                        file_path = str(file_id).replace("LOCAL:", "")
                        if not os.path.exists(file_path):
                            logging.warning(f"Immediate saved file {file_path} not found. Attempting re-download.")
                            file_path = None # Reset to attempt re-download
                    
                    if not file_path: # Only attempt download if not already saved
                        try:
                            logging.info(f"Step 1: Attempting RAM download for {media_type}...")
                            try:
                               file_bytes = await client.download_media(message, in_memory=True)
                               if file_bytes:
                                   logging.info(f"Step 2: RAM download successful. Type of data: {type(file_bytes)}")
                                   ts = int(datetime.datetime.now().timestamp())
                                   ext = ".bin"
                                   if media_type == "voice": ext = ".ogg"
                                   elif media_type == "video_note": ext = ".mp4"
                                   elif media_type == "photo": ext = ".jpg"
                                   elif media_type == "video": ext = ".mp4"
                                   
                                   os.makedirs("downloads", exist_ok=True)
                                   fname = f"downloads/secret_{ts}{ext}"
                                   manual_path = os.path.abspath(fname)
                                   
                                   logging.info(f"Step 3: Writing to file: {manual_path}")
                                   with open(manual_path, "wb") as f:
                                       if hasattr(file_bytes, "getbuffer"): f.write(file_bytes.getbuffer())
                                       elif hasattr(file_bytes, "read"): f.write(file_bytes.read())
                                       else: f.write(file_bytes)
                                   
                                   if os.path.exists(manual_path):
                                       file_path = manual_path
                                       logging.info(f"Step 4: File successfully created at {file_path}")
                                   else:
                                       logging.error(f"Step 4 ERROR: File was not created at {manual_path}!")
                               else:
                                   logging.warning("Step 2: RAM download returned None.")
                            except Exception as ram_e:
                               logging.warning(f"RAM download error: {ram_e}")
                               
                            # Priority 2: Standard Download if RAM failed
                            if not file_path:
                                logging.info(f"Step 5: Falling back to standard download...")
                                file_path = await message.download()
                                if file_path:
                                    logging.info(f"Step 6: Standard download successful saved to {file_path}")
                                else:
                                    logging.error("Step 6: Standard download returned None.")

                        except Exception as dl_e:
                            logging.error(f"CRITICAL Download error: {dl_e}", exc_info=True)

                    if file_path:
                        user_tag = f"@{s_username}" if s_username else s_name
                        caption = f"🔐 Секретное медиа от {user_tag}\n📁 Чат: {message.chat.title or 'Личный'}"
                        try:
                            inp = FSInputFile(file_path)
                            sent_msg = None
                            caption = f"🔐 Секретное медиа от {s_name} (@{s_username if s_username else 'None'})\n📁 Чат: {message.chat.title or 'Личный'}"
                            
                            is_voice = (media_type == "voice") or str(file_path).endswith(".ogg")
                            is_video_note = (media_type == "video_note") or (str(file_path).endswith(".mp4") and "video_note" in str(file_path))
                            
                            if is_voice: sent_msg = await bot.send_voice(user_id, inp, caption=caption)
                            elif is_video_note: sent_msg = await bot.send_video_note(user_id, inp); await bot.send_message(user_id, caption)
                            elif media_type == "photo": sent_msg = await bot.send_photo(user_id, inp, caption=caption)
                            elif media_type == "video": sent_msg = await bot.send_video(user_id, inp, caption=caption)
                            else: sent_msg = await bot.send_document(user_id, inp, caption=caption)
                        except Exception as send_e:
                             logging.error(f"Error during bot send: {send_e}")
                             try: await client.send_document("me", file_path, caption=f"Fallback save: {caption}")
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
                                        path = None
                                        if str(fid).startswith("LOCAL:"):
                                            path = str(fid).replace("LOCAL:", "")
                                            if not os.path.exists(path):
                                                logging.warning(f"Local file {path} not found for deleted message.")
                                                path = None # File not found, try downloading
                                        
                                        if not path: # If not local or local file not found, download
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
                                            if os.path.exists(path) and not str(fid).startswith("LOCAL:"): # Only remove if not a local cached file
                                                os.remove(path)
                                    except: pass # alert += "\n❌ Не удалось скачать."
                                
                                await bot.send_message(user_id, alert)
                                database.delete_cached_message(orig_id, chat_id)
                                
                    except Exception as e:
                        # logging.error(f"Check chat {chat_id} failed: {e}")
                        pass

        except Exception as e:
            logging.error(f"Check deleted loop error: {e}")

ub_manager = UserBotManager()
