"""
Global error handler for @InstaOhang_bot.
Catches all unhandled exceptions, logs them safely (no token/password leakage),
and sends a user-friendly error message.
"""

import logging
import traceback
from aiogram import Router
from aiogram.types import ErrorEvent, Update

logger = logging.getLogger(__name__)

error_router = Router()

# ─────────────────────────────────────────────────────────────────────────────
# Safe error message shown to users (no stack trace, no internals)
# ─────────────────────────────────────────────────────────────────────────────
USER_ERROR_MSG = (
    "❌ <b>Xatolik yuz berdi.</b>\n\n"
    "Iltimos, birozdan keyin qayta urinib ko'ring.\n"
    "Muammo davom etsa, @htpAsilbek ga murojaat qiling."
)


@error_router.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    """
    Catches all unhandled exceptions from any handler.
    - Logs full traceback to server logs
    - Sends safe, generic message to user
    - Never exposes stack trace, token, or passwords to users
    """
    exc = event.exception
    update: Update = event.update

    # Log the full error server-side (safe logging — no token/password in exc)
    logger.error(
        f"[ERROR] Unhandled exception in update #{update.update_id if update else '?'}: "
        f"{type(exc).__name__}: {exc}\n"
        f"{traceback.format_exc()}"
    )

    # Try to notify the user with a safe message
    try:
        if update and update.message:
            await update.message.answer(USER_ERROR_MSG, parse_mode="HTML")
        elif update and update.callback_query:
            await update.callback_query.answer(
                "❌ Xatolik yuz berdi. Qayta urinib ko'ring.", show_alert=True
            )
            try:
                await update.callback_query.message.answer(USER_ERROR_MSG, parse_mode="HTML")
            except Exception:
                pass
    except Exception as notify_err:
        logger.warning(f"[ERROR] Could not notify user about error: {notify_err}")

    # Return True to tell aiogram the error is handled
    return True
