#!/usr/bin/env python3
"""
FEBVS / CASH-3V Daily Question Bot
Generates 5 hard vascular surgery questions and sends them via Telegram.
Each question gets its own message with inline answer buttons.
"""

import os
import json
import random
import asyncio
import httpx

# ── Config (set these as environment variables / GitHub Secrets) ──────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ── Topic pool (alternates between FEBVS and CASH-3V style) ──────────────────
TOPICS = [
    "Abdominal aortic aneurysm — EVAR indications, endoleak classification, surveillance",
    "Carotid artery disease — CEA vs CAS, NASCET criteria, perioperative management",
    "Peripheral arterial disease — CLTI, WIfI classification, bypass vs endovascular",
    "Chronic venous insufficiency — CEAP classification, EVLA, DVT management",
    "Acute limb ischaemia — Rutherford classification, embolus vs thrombosis, fasciotomy",
    "Diabetic foot — WIfI scoring, revascularisation, multidisciplinary management",
    "Renal artery disease — FMD vs atherosclerotic, renovascular hypertension, treatment",
    "Mesenteric ischaemia — acute vs chronic, NOMI, endovascular vs open",
    "Vascular trauma — damage control, REBOA, iatrogenic injuries, TEVAR for blunt aortic injury",
    "Coagulation and anticoagulation — HIT, DOAC reversal, perioperative bridging",
    "Thoracic aorta — type B dissection, TEVAR indications, spinal cord protection",
    "Vascular access — AV fistula maturation, steal syndrome, DRIL procedure",
    "Rare vascular conditions — FMD, Takayasu, popliteal entrapment, cystic adventitial disease",
    "Endovascular techniques — wire/catheter selection, stent types, complication bailout",
    "Aorto-iliac occlusive disease — TASC classification, aorto-bifemoral bypass, kissing stents",
]

# ── Generate questions via Anthropic API ──────────────────────────────────────
async def generate_questions(topic: str) -> list[dict]:
    prompt = (
        f"FEBVS/CASH-3V exam. Generate 5 HARD vascular surgery MCQs on: \"{topic}\". "
        "Require detailed specialist knowledge — specific thresholds, trial data, exceptions, "
        "complication management. Plausible distractors. "
        "Respond ONLY with JSON, no markdown:\n"
        "{\"questions\":[{\"question\":\"...\",\"options\":[\"A. ...\",\"B. ...\",\"C. ...\",\"D. ...\",\"E. ...\"],\"correct\":0,\"explanation\":\"...\"}]}"
    )
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",  # Haiku = much faster + cheaper for daily use
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        raw = "".join(b.get("text", "") for b in data["content"]).strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)["questions"]


# ── Send via Telegram ─────────────────────────────────────────────────────────
async def send_telegram(text: str, parse_mode: str = "HTML") -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        })
        resp.raise_for_status()


async def send_poll(question: str, options: list[str], correct_idx: int, explanation: str) -> None:
    """Send question as a Telegram Quiz poll (auto-grades, shows explanation on answer)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    # Telegram poll options max 100 chars each — truncate if needed
    clean_options = [o[3:].strip() if o[1] == "." else o for o in options]  # strip "A. " prefix
    clean_options = [o[:100] for o in clean_options]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "question": question[:300],  # Telegram max 300 chars for poll question
            "options": clean_options,
            "type": "quiz",
            "correct_option_id": correct_idx,
            "explanation": explanation[:200],  # Telegram max 200 chars
            "is_anonymous": False,
            "open_period": 86400,  # Poll open for 24 hours
        })
        resp.raise_for_status()


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    # Pick a random topic for today
    topic = random.choice(TOPICS)

    print(f"Generating questions on: {topic}")
    questions = await generate_questions(topic)
    print(f"Got {len(questions)} questions")

    # Send header message
    await send_telegram(
        f"🩺 <b>Daily Vascular Surgery Questions</b>\n\n"
        f"📚 Today's topic: <i>{topic}</i>\n\n"
        f"5 hard questions — answer each poll below. "
        f"Good luck! 💪"
    )
    await asyncio.sleep(1)

    # Send each question as a Telegram Quiz poll
    for i, q in enumerate(questions[:5], 1):
        print(f"Sending question {i}...")
        try:
            await send_poll(
                question=f"Q{i}: {q['question']}",
                options=q["options"],
                correct_idx=q["correct"],
                explanation=q["explanation"][:200],
            )
        except Exception as e:
            # Fallback: if poll fails (e.g. question too long), send as text
            print(f"Poll failed for Q{i}: {e} — falling back to text")
            opts = "\n".join(q["options"])
            await send_telegram(
                f"<b>Q{i}:</b> {q['question']}\n\n{opts}\n\n"
                f"<tg-spoiler>✅ Answer: {q['options'][q['correct']]}\n\n{q['explanation']}</tg-spoiler>"
            )
        await asyncio.sleep(1.5)  # Avoid Telegram rate limits

    # Send closing message
    await send_telegram(
        "✅ <b>That's all for today!</b>\n\n"
        "Open the study app for more practice:\n"
        "Keep it up — consistency beats cramming. 🎯"
    )
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
