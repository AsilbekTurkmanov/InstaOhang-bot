import os
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from services.ffmpeg_service import convert_to_round_video
from utils.helpers import safe_remove_files, clean_html, check_file_size

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("round"))
async def cmd_round(message: Message):
    """
    Converts replied video into a circular Video Note (Dumaloq Video).
    Triggered when user replies to any video message with /round.
    """
    target_msg = message.reply_to_message if message.reply_to_message else message
    
    # Check if target message has a video or video note
    video = target_msg.video or target_msg.animation or target_msg.document
    if not video or (target_msg.document and not target_msg.document.mime_type.startswith("video/")):
        await message.answer(
            "⚠️ <b>Iltimos, dumaloq video qilish uchun biror bir videoga javob (reply/otvetit) bergan holda <code>/round</code> deb yozing!</b>",
            parse_mode="HTML"
        )
        return

    status_msg = await message.answer("⭕ <b>Videoni dumaloq shaklga keltirish qilinmoqda...</b>\n<i>Iltimos kuting ⏳</i>", parse_mode="HTML")
    
    file_id = video.file_id
    temp_in = f"downloads/round_in_{message.from_user.id}_{message.message_id}.mp4"
    
    try:
        # Download video from Telegram
        tg_file = await message.bot.get_file(file_id)
        await message.bot.download_file(tg_file.file_path, temp_in)
        
        # Convert to circular video note (1:1 aspect ratio, 640x640)
        output_round = await convert_to_round_video(temp_in)
        
        is_valid, size_mb = check_file_size(output_round)
        if not is_valid:
            await status_msg.edit_text(f"⚠️ <b>Dumaloq video hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML")
            safe_remove_files(temp_in, output_round)
            return

        # Send as video note
        round_input = FSInputFile(output_round)
        await message.answer_video_note(video_note=round_input)
        await status_msg.delete()
        
        # Clean up temp files
        safe_remove_files(temp_in, output_round)
        
    except Exception as e:
        logger.error(f"Error in /round handler: {e}")
        await status_msg.edit_text(f"❌ <b>Dumaloq video tayyorlashda xatolik yuz berdi:</b>\n{clean_html(str(e))}", parse_mode="HTML")
        safe_remove_files(temp_in)
