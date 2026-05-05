import asyncio
import io
import logging
import random
from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..ai.client import MissingAPIKeyError
from ..ai.resume_builder import apply_patches, build_docx, build_pdf
from ..ai.scorer import ScoreResult, load_resume
from ..ai.tailor import tailor_resume
from ..config import settings
from ..database import (
    applies_today_count,
    get_alert_job_id,
    get_job,
    record_alert,
    set_alert_status,
)
from ..scrapers.base import Job

log = logging.getLogger(__name__)


def _format(job: Job, score: ScoreResult | None) -> str:
    lines = [
        f"<b>{escape(job.title)}</b>",
        (
            f"{escape(job.company or job.source.title())}"
            f"{' — ' + escape(job.location) if job.location else ''}"
        ),
        f"<i>source: {escape(job.source)}</i>",
    ]
    if score is not None:
        lines.append("")
        lines.append(f"<b>ATS score:</b> {score.score}/100")
        lines.append(f"<i>{escape(score.rationale)}</i>")
        if score.matched_keywords:
            lines.append(f"✓ matched: {escape(', '.join(score.matched_keywords[:8]))}")
        if score.missing_keywords:
            lines.append(f"✗ missing: {escape(', '.join(score.missing_keywords[:8]))}")
    lines.append("")
    lines.append(f"<a href=\"{escape(job.url, quote=True)}\">Open posting</a>")
    return "\n".join(lines)


def _seconds_until_quiet_ends(now: datetime | None = None) -> float:
    """0 if not in quiet hours; otherwise seconds to wait until quiet_hours_end."""
    start = settings.quiet_hours_start
    end = settings.quiet_hours_end
    if start == end:
        return 0.0
    tz = ZoneInfo(settings.search_timezone)
    now = now or datetime.now(tz)
    h = now.hour
    in_quiet = (start <= h or h < end) if start > end else (start <= h < end)
    if not in_quiet:
        return 0.0
    target = now.replace(hour=end, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _job_from_row(row: dict) -> Job:
    job = Job(
        source=row["source"],
        title=row["title"],
        company=row.get("company") or "",
        location=row.get("location") or "",
        url=row["url"],
        description=row.get("description") or "",
    )
    return job


class TelegramNotifier:
    def __init__(self) -> None:
        self.app: Application = (
            Application.builder().token(settings.telegram_bot_token).build()
        )
        self.app.add_handler(CallbackQueryHandler(self._on_callback))

    async def start(self) -> None:
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        log.info("Telegram bot started")

    async def stop(self) -> None:
        try:
            await self.app.updater.stop()
        except Exception:
            pass
        await self.app.stop()
        await self.app.shutdown()

    async def send_job(self, job: Job, score: ScoreResult | None = None) -> None:
        delay = random.uniform(
            settings.notify_delay_min_seconds,
            settings.notify_delay_max_seconds,
        )
        log.info("Queued alert for %s — delaying %.0fs (anti-flag)", job.title, delay)
        await asyncio.sleep(delay)

        quiet_wait = _seconds_until_quiet_ends()
        if quiet_wait > 0:
            log.info(
                "Quiet hours active — deferring %s by %.0fs (%.1fh)",
                job.title, quiet_wait, quiet_wait / 3600,
            )
            await asyncio.sleep(quiet_wait)

        if await applies_today_count() >= settings.max_applies_per_day:
            log.info("Daily apply cap reached, suppressing alert for %s", job.title)
            return

        alert_id = await record_alert(job.job_id)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{alert_id}"),
            InlineKeyboardButton("⏭ Skip", callback_data=f"skip:{alert_id}"),
        ]])
        await self.app.bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=_format(job, score),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
            reply_markup=keyboard,
        )

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        try:
            action, alert_id_str = query.data.split(":", 1)
            alert_id = int(alert_id_str)
        except (ValueError, AttributeError):
            return

        status = "approved" if action == "approve" else "skipped"
        await set_alert_status(alert_id, status)

        suffix = "\n\n✅ <b>Approved — tailoring resume…</b>" if status == "approved" else "\n\n⏭ <b>Skipped</b>"
        original = query.message.text_html if query.message else ""
        await query.edit_message_text(
            text=original + suffix,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )

        if status == "approved" and query.message:
            chat_id = query.message.chat_id
            message_id = query.message.message_id
            asyncio.create_task(
                self._deliver_tailored(alert_id, chat_id, message_id, original)
            )

    async def _set_status_suffix(
        self, chat_id: int, message_id: int, original: str, suffix: str,
    ) -> None:
        try:
            await self.app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=original + suffix,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        except Exception as exc:
            log.warning("Failed to update alert message status: %s", exc)

    async def _deliver_tailored(
        self, alert_id: int, chat_id: int, message_id: int, original: str,
    ) -> None:
        job_id = await get_alert_job_id(alert_id)
        if not job_id:
            log.warning("Approve for unknown alert %d", alert_id)
            await self._set_status_suffix(
                chat_id, message_id, original,
                "\n\n⚠️ <b>Approved — internal error (alert not found)</b>",
            )
            return
        row = await get_job(job_id)
        if not row:
            log.warning("Approve for alert %d: job %s not found", alert_id, job_id)
            await self._set_status_suffix(
                chat_id, message_id, original,
                "\n\n⚠️ <b>Approved — internal error (job not found)</b>",
            )
            return
        job = _job_from_row(row)
        resume = load_resume()

        tailor_status = "tailored"  # tailored | base | failed
        failure_msg = ""
        try:
            patches = await tailor_resume(job, resume)
        except MissingAPIKeyError:
            tailor_status = "base"
            failure_msg = "ANTHROPIC_API_KEY not set"
            patches = []
        except Exception as exc:
            log.exception("Tailor failed for %s: %s", job.title, exc)
            tailor_status = "failed"
            failure_msg = str(exc)
            patches = []

        tailored = apply_patches(resume, patches) if patches else resume
        try:
            pdf_bytes = build_pdf(tailored)
            docx_bytes = build_docx(tailored)
        except Exception as exc:
            log.exception("Resume build failed for %s: %s", job.title, exc)
            await self._set_status_suffix(
                chat_id, message_id, original,
                f"\n\n⚠️ <b>Approved — resume build failed:</b> {escape(str(exc))}",
            )
            return

        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in job.title)[:60].strip() or "job"
        base = f"Resume_{safe_title}"

        caption = f"📄 Tailored PDF — {len(patches)} patch(es) applied"
        if tailor_status != "tailored":
            caption = f"📄 Base PDF (no tailoring — {failure_msg})"

        await self.app.bot.send_document(
            chat_id=chat_id,
            document=InputFile(io.BytesIO(pdf_bytes), filename=f"{base}.pdf"),
            caption=caption,
        )
        await self.app.bot.send_document(
            chat_id=chat_id,
            document=InputFile(io.BytesIO(docx_bytes), filename=f"{base}.docx"),
        )

        if tailor_status == "tailored":
            final = f"\n\n✅ <b>Approved — resume tailored ({len(patches)} patch(es))</b>"
        elif tailor_status == "base":
            final = f"\n\n✅ <b>Approved — base resume sent</b> (<i>{escape(failure_msg)}</i>)"
        else:
            final = f"\n\n⚠️ <b>Approved — tailor failed:</b> {escape(failure_msg)} <i>(base resume sent)</i>"
        await self._set_status_suffix(chat_id, message_id, original, final)
