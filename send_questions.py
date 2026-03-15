#!/usr/bin/env python3
import os
import json
import random
import asyncio
import httpx

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TOPICS = [
    "Abdominal aortic aneurysm — EVAR indications, endoleak classification, surveillance",
    "Carotid artery disease — CEA vs CAS, NASCET criteria, perioperative management",
    "Peripheral arterial disease — CLTI, WIfI classification, bypass vs endovascular",
    "Chronic venous insufficiency — CEAP classification, EVLA, DVT management",
    "Acute limb ischaemia — Rutherford classification, embolus vs thrombosis, fasciotomy",
    "Diabetic foot — WIfI scoring, revascularisation, multidisciplinary management",
    "Renal artery disease — FMD vs atherosclerotic, renovascular hypertension, treatment",
    "Mesenteric ischaemia — acute vs chronic, NOMI, endovascular vs open",
    "Vascular trauma — damage control, REBOA, iatrogenic injuries, TEVAR",
    "Coagulation — HIT, DOAC reversal, perioperative anticoagulation",
    "Thoracic aorta — type B dissection, TEVAR indications, spinal cord protection",
    "Vascular access — AV fistula maturation, steal syndrome, DRIL procedure",
    "Endovascular techniques — wire selection, stent types, complication bailout",
    "Aorto-iliac occlusive disease — TASC classification, bypass, kissing stents",
]


async def generate_questions(topic: str) -> list:
    system = (
        "You are a medical exam question writer. "
        "Always respond with ONLY a JSON object — no prose, no markdown, no backticks. "
        "Keep every answer option under 12 words. "
        "Keep every explanation under 80 words."
    )
    user = (
        f"Write 3 hard MCQs about: {topic}\n"
        "Questions should be detailed clinical scenarios (1-3 sentences) requiring specialist knowledge. "
        "Use specific numbers, trial data, or nuanced decision-making. "
        "Return this exact JSON structure:\n"
        '{"questions":[{"question":"...","options":["A. ...","B. ...","C. ...","D. ...","E. ..."],"correct":0,"explanation":"..."}]}'
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
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 8000,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

        print("API response:", json.dumps(data, indent=2))

        raw = "".join(b.get("text", "") for b in data["content"]).strip()
        print(f"Raw text ({len(raw)} chars):\n{raw}")

        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)["questions"]


async def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        })
        resp.raise_for_status()


async def send_poll(q: dict, num: int) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    options = [o[3:].strip() if len(o) > 2 and o[1] == "." else o for o in q["options"]]
    options = [o[:100] for o in options]
    explanation = q["explanation"][:400]
    question_text = f"Q{num}: {q['question']}"[:300]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "question": question_text,
            "options": options,
            "type": "quiz",
            "correct_option_id": q["correct"],
            "explanation": explanation,
            "is_anonymous": False,
            # no open_period = poll stays open indefinitely
        })
        if resp.status_code != 200:
            print(f"Poll failed: {resp.text} — sending as text instead")
            opts = "\n".join(q["options"])
            await send_telegram(
                f"<b>Q{num}:</b> {q['question']}\n\n{opts}\n\n"
                f"<tg-spoiler>✅ {q['options'][q['correct']]}\n{q['explanation']}</tg-spoiler>"
            )


async def main():
    topic = random.choice(TOPICS)
    print(f"Topic: {topic}")

    questions = await generate_questions(topic)
    print(f"Got {len(questions)} questions")

    await send_telegram(
        f"🩺 <b>Daily Vascular Surgery Questions</b>\n\n"
        f"📚 <i>{topic}</i>\n\n"
        f"3 hard questions below 👇"
    )
    await asyncio.sleep(1)

    for i, q in enumerate(questions[:3], 1):
        print(f"Sending Q{i}...")
        await send_poll(q, i)
        await asyncio.sleep(1.5)

    await send_telegram("✅ <b>Done for today!</b> Keep it up 💪")
    print("All done.")


if __name__ == "__main__":
    asyncio.run(main())
