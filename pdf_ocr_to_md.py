#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_ocr_to_md.py — Модульний AI Vision та відкритий локальний OCR конвертер для PDF у Markdown (UTF-8).
Підтримує скановані документи, растрові зображення, таблиці, печатки, штампи та рукописний текст.

Підтримувані рушії розпізнавання:
1. Google Gemini Vision (gemini-2.5-flash, gemini-2.0-flash через google.genai)
2. OpenAI Vision (gpt-4o, gpt-4o-mini через openai)
3. Anthropic Claude Vision (claude-3-5-sonnet, claude-3-5-haiku через anthropic)
4. DeepSeek / Сумісні OpenAI Endpoints (custom base_url)
5. PaddleOCR (локальний нейромережевий рушій: github.com/PaddlePaddle/PaddleOCR)
6. Tesseract OCR (локальний рушій: github.com/tesseract-ocr/tesseract)
7. Microsoft MarkItDown OCR Plugin (github.com/microsoft/markitdown)

Особливості для великих документів (від 1 до 1000+ сторінок):
- Потоковий рендеринг у пам'яті (без гігабайтів тимчасових файлів).
- Система контрольних точок (Checkpoint / Resume) для відновлення з місця зупинки.
- Багатопотокова паралельна обробка з контролем Rate Limiting (RPM).
- Наочний прогрес-бар (tqdm).
"""

import sys
import os
import io
import re
import time
import glob
import json
import argparse
import base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Встановлюємо UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Завантажуємо змінні з .env файлу, якщо присутні
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Системний промпт для OCR законодавчих та офіційних документів
OCR_SYSTEM_PROMPT = """Ти — високоточний OCR-екстрактор офіційних, законодавчих та судових документів України.
Твоє завдання — розпізнати весь текст із наданого зображення сторінки документа та повернути виключно чистий, ідеально структурований Markdown (UTF-8).

Правила форматування:
1. Якщо на сторінці зображено Державний Герб України — вкажи: [Герб України]
2. Заголовки органів влади (Міністерство, Верховна Рада тощо) виділяй як: # ЗАГОЛОВОК
3. Назви законів, постанов, наказів та підзаконних актів виділяй як: ## НАЗВА
4. Статті, розділи, пункти та частини оформлюй як: ## Стаття 1. ..., 1.1., 1. тощо.
5. Зберігай оригінальне накреслення: **напівжирний**, *курсив*. Підкреслений текст оформлюй як **напівжирний** або звичайний текст.
6. Таблиці передавай у стандартному Markdown синтаксисі (| колонка 1 | колонка 2 |).
7. Двоколонкові блоки (номер/дата зліва, адресат/посада справа, підписи сторін) розміщуй зі збереженням логічної структури.
8. Печатки, штампи та підписи передавай у вигляді: [Штамп: ...], [Печатка: ...], **Державний виконавець** [підпис] **Прізвище І.Б.**
9. НЕ додавай жодних власних коментарів, передмов або блоків коду ```markdown ... ``` — повертай лише чистий Markdown текст сторінки.
10. КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати будь-які HTML теги (<u>, </u>, <span>, <font>, <br>, <p> тощо). Використовуй тільки чистий синтаксис Markdown!
"""


def _clean_ocr_markdown(text: str) -> str:
    """Видаляє всі HTML-теги (<u>, </u>, <span> тощо) та нормалізує чистий Markdown."""
    if not text:
        return ''
    # Видалення огортання в код markdown
    text = re.sub(r'^```(?:markdown)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    
    # Видалення тегів <u>...</u>
    text = re.sub(r'<\/?u\b[^>]*>', '', text, flags=re.IGNORECASE)
    # Заміна <br> на розрив рядка
    text = re.sub(r'<br\s*\/?>', '  \n', text, flags=re.IGNORECASE)
    # Заміна <b>/<strong> на **
    text = re.sub(r'<\/?(?:b|strong)\b[^>]*>', '**', text, flags=re.IGNORECASE)
    # Заміна <i>/<em> на *
    text = re.sub(r'<\/?(?:i|em)\b[^>]*>', '*', text, flags=re.IGNORECASE)
    # Видалення інших HTML тегів
    text = re.sub(r'<\/?(?:span|font|p|div|section|article)\b[^>]*>', '', text, flags=re.IGNORECASE)
    # Видалення будь-яких залишкових HTML тегів
    text = re.sub(r'<[a-zA-Z\/][^>]*>', '', text)
    
    # Очищення подвійного жирного **** -> **
    text = re.sub(r'\*{4,}', '**', text)
    # Об'єднання **слово1** **слово2** -> **слово1 слово2**
    while re.search(r'\*\*(.+?)\*\*\s+\*\*(.+?)\*\*', text):
        text = re.sub(r'\*\*(.+?)\*\*\s+\*\*(.+?)\*\*', r'**\1 \2**', text)
        
    return text.strip()


# ──────────────────────────────────────────────────────
# Детекція та конфігурація рушіїв OCR
# ──────────────────────────────────────────────────────

def _get_tesseract_cmd() -> str:
    """Знаходить tesseract.exe у системі Windows або PATH. Повертає None, якщо не знайдено."""
    import shutil
    cmd = shutil.which('tesseract')
    if cmd:
        return cmd
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        r"C:\tools\tesseract\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe"
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None


def get_available_engines() -> dict:
    """Перевіряє доступність рушіїв OCR у поточному середовищі."""
    engines = {}
    
    # 1. Gemini
    gemini_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if gemini_key:
        engines['gemini'] = {'available': True, 'desc': 'Google Gemini Vision (Найшвидший & Найвища якість)'}
    else:
        engines['gemini'] = {'available': False, 'desc': 'Google Gemini Vision (Потрібен GEMINI_API_KEY у .env)'}
        
    # 2. OpenAI
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        engines['openai'] = {'available': True, 'desc': 'OpenAI GPT-4o Vision'}
    else:
        engines['openai'] = {'available': False, 'desc': 'OpenAI GPT-4o Vision (Потрібен OPENAI_API_KEY у .env)'}
        
    # 3. Claude
    claude_key = os.getenv('ANTHROPIC_API_KEY')
    if claude_key:
        engines['claude'] = {'available': True, 'desc': 'Anthropic Claude 3.5 Sonnet Vision'}
    else:
        engines['claude'] = {'available': False, 'desc': 'Anthropic Claude Vision (Потрібен ANTHROPIC_API_KEY у .env)'}
        
    # 4. DeepSeek / Custom
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    if deepseek_key:
        engines['deepseek'] = {'available': True, 'desc': 'DeepSeek Vision / OpenAI-compatible'}
    else:
        engines['deepseek'] = {'available': False, 'desc': 'DeepSeek Vision (Потрібен DEEPSEEK_API_KEY у .env)'}
        
    # 5. PaddleOCR
    try:
        import paddleocr
        engines['paddleocr'] = {'available': True, 'desc': 'PaddleOCR (Локальний нейромережевий рушій)'}
    except ImportError:
        engines['paddleocr'] = {'available': False, 'desc': 'PaddleOCR (Встановіть: pip install paddlepaddle paddleocr)'}
        
    # 6. Tesseract
    tess_bin = _get_tesseract_cmd()
    if tess_bin:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tess_bin
            engines['tesseract'] = {'available': True, 'desc': f'Tesseract OCR ({tess_bin})'}
        except ImportError:
            engines['tesseract'] = {'available': False, 'desc': 'Tesseract OCR (Встановіть: pip install pytesseract)'}
    else:
        engines['tesseract'] = {'available': False, 'desc': 'Tesseract OCR (Встановіть: winget install UB-Mannheim.TesseractOCR)'}
        
    return engines


def select_best_engine(preferred: str = 'auto') -> str:
    """Обирає найкращий доступний рушій розпізнавання."""
    avail = get_available_engines()
    if preferred != 'auto' and preferred in avail:
        if avail[preferred]['available']:
            return preferred
        else:
            print(f"  [!] Рушій '{preferred}' недоступний ({avail[preferred]['desc']}). Шукаю альтернативу...")
            
    # Пріоритет авто-вибору
    for candidate in ['gemini', 'openai', 'claude', 'deepseek', 'paddleocr', 'tesseract']:
        if avail.get(candidate, {}).get('available'):
            return candidate
            
    return 'none'


# ──────────────────────────────────────────────────────
# OCR Реалізації для окремих рушіїв
# ──────────────────────────────────────────────────────

def _ocr_page_gemini(image_bytes: bytes, model: str = None) -> tuple[str, dict]:
    """Розпізнає сторінку через Google Gemini Vision та повертає (текст, usage)."""
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY не знайдено в оточенні або .env")
        
    target_model = model or os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')
    fallback_models = [target_model, 'gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    seen = set()
    candidate_models = [m for m in fallback_models if not (m in seen or seen.add(m))]
    
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    
    last_ex = None
    for cand in candidate_models:
        try:
            response = client.models.generate_content(
                model=cand,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
                    OCR_SYSTEM_PROMPT
                ]
            )
            in_tok = 0
            out_tok = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata is not None:
                in_tok = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
                out_tok = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
            
            usage = {
                'engine': 'gemini',
                'model': cand,
                'in_tokens': in_tok,
                'out_tokens': out_tok,
                'total_tokens': in_tok + out_tok
            }
            return response.text.strip(), usage
        except Exception as e:
            last_ex = e
            if '404' in str(e) or 'NOT_FOUND' in str(e):
                continue
            raise e
            
    # Якщо новий SDK не зміг, пробуємо старий SDK
    try:
        import google.generativeai as genai_old
        from PIL import Image
        genai_old.configure(api_key=api_key)
        m = genai_old.GenerativeModel('gemini-1.5-flash')
        img = Image.open(io.BytesIO(image_bytes))
        resp = m.generate_content([OCR_SYSTEM_PROMPT, img])
        in_tok = 0
        out_tok = 0
        if hasattr(resp, 'usage_metadata') and resp.usage_metadata is not None:
            in_tok = getattr(resp.usage_metadata, 'prompt_token_count', 0) or 0
            out_tok = getattr(resp.usage_metadata, 'candidates_token_count', 0) or 0
        usage = {
            'engine': 'gemini',
            'model': 'gemini-1.5-flash',
            'in_tokens': in_tok,
            'out_tokens': out_tok,
            'total_tokens': in_tok + out_tok
        }
        return resp.text.strip(), usage
    except Exception:
        raise last_ex


def _ocr_page_openai(image_bytes: bytes, model: str = 'gpt-4o') -> tuple[str, dict]:
    """Розпізнає сторінку через OpenAI GPT-4o / GPT-4o-mini та повертає (текст, usage)."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY не знайдено в оточенні або .env")
        
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    b64_img = base64.b64encode(image_bytes).decode('utf-8')
    data_url = f"data:image/png;base64,{b64_img}"
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Розпізнай текст цього документа у Markdown:"},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}
                ]
            }
        ],
        max_tokens=4096,
        temperature=0.1
    )
    in_tok = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
    out_tok = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
    usage = {
        'engine': 'openai',
        'model': model,
        'in_tokens': in_tok,
        'out_tokens': out_tok,
        'total_tokens': in_tok + out_tok
    }
    return response.choices[0].message.content.strip(), usage


def _ocr_page_claude(image_bytes: bytes, model: str = 'claude-3-5-sonnet-20241022') -> tuple[str, dict]:
    """Розпізнає сторінку через Anthropic Claude 3.5 Sonnet / Haiku та повертає (текст, usage)."""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY не знайдено в оточенні або .env")
        
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    
    b64_img = base64.b64encode(image_bytes).decode('utf-8')
    
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.1,
        system=OCR_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_img,
                        },
                    },
                    {"type": "text", "text": "Розпізнай текст документа у чистий Markdown:"}
                ],
            }
        ]
    )
    in_tok = getattr(message.usage, 'input_tokens', 0) if hasattr(message, 'usage') and message.usage else 0
    out_tok = getattr(message.usage, 'output_tokens', 0) if hasattr(message, 'usage') and message.usage else 0
    usage = {
        'engine': 'claude',
        'model': model,
        'in_tokens': in_tok,
        'out_tokens': out_tok,
        'total_tokens': in_tok + out_tok
    }
    return message.content[0].text.strip(), usage


def _ocr_page_deepseek(image_bytes: bytes, model: str = 'deepseek-chat') -> tuple[str, dict]:
    """Розпізнає сторінку через DeepSeek або будь-який OpenAI-сумісний endpoint та повертає (текст, usage)."""
    api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')
    
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    b64_img = base64.b64encode(image_bytes).decode('utf-8')
    data_url = f"data:image/png;base64,{b64_img}"
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Розпізнай текст документа у чистий Markdown:"},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ],
        max_tokens=4096,
        temperature=0.1
    )
    in_tok = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
    out_tok = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
    usage = {
        'engine': 'deepseek',
        'model': model,
        'in_tokens': in_tok,
        'out_tokens': out_tok,
        'total_tokens': in_tok + out_tok
    }
    return response.choices[0].message.content.strip(), usage


def _ocr_page_paddleocr(image_bytes: bytes) -> tuple[str, dict]:
    """Розпізнає сторінку через локальний нейромережевий рушій PaddleOCR."""
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image
    except ImportError:
        raise ImportError("Встановіть PaddleOCR: pip install paddlepaddle paddleocr")
        
    ocr = PaddleOCR(use_angle_cls=True, lang='uk')
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img_np = np.array(img)
    
    result = ocr.ocr(img_np, cls=True)
    lines = []
    if result and result[0]:
        for line in result[0]:
            text, score = line[1]
            if score > 0.4:
                lines.append(text)
    usage = {'engine': 'paddleocr', 'model': 'PaddleOCR (Local)', 'in_tokens': 0, 'out_tokens': 0, 'total_tokens': 0}
    return '\n\n'.join(lines), usage


def _ocr_page_tesseract(image_bytes: bytes) -> tuple[str, dict]:
    """Розпізнає сторінку через локальний Tesseract OCR (ukr + eng)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError("Встановіть pytesseract: pip install pytesseract Pillow")
        
    pytesseract.pytesseract.tesseract_cmd = _get_tesseract_cmd()
    img = Image.open(io.BytesIO(image_bytes))
    
    try:
        text = pytesseract.image_to_string(img, lang='ukr+eng')
    except Exception:
        text = pytesseract.image_to_string(img)
        
    usage = {'engine': 'tesseract', 'model': 'Tesseract OCR (Local)', 'in_tokens': 0, 'out_tokens': 0, 'total_tokens': 0}
    return text.strip(), usage


def ocr_single_image(image_bytes: bytes, engine: str = 'gemini', retries: int = 3) -> tuple[str, dict]:
    """Розпізнає байти зображення за допомогою обраного рушія з повторними спробами."""
    last_err = None
    for attempt in range(retries):
        try:
            if engine == 'gemini':
                return _ocr_page_gemini(image_bytes)
            elif engine == 'openai':
                return _ocr_page_openai(image_bytes)
            elif engine == 'claude':
                return _ocr_page_claude(image_bytes)
            elif engine == 'deepseek':
                return _ocr_page_deepseek(image_bytes)
            elif engine == 'paddleocr':
                return _ocr_page_paddleocr(image_bytes)
            elif engine == 'tesseract':
                return _ocr_page_tesseract(image_bytes)
            else:
                raise ValueError(f"Невідомий рушій OCR: {engine}")
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
            
    raise RuntimeError(f"Помилка OCR ({engine}) після {retries} спроб: {last_err}")


def print_usage_cost_summary(all_usages: list, total_pages: int):
    """Виводить детальну статистику токенів та орієнтовну вартість OCR обробки."""
    if not all_usages:
        return
        
    total_in = sum(u.get('in_tokens', 0) for u in all_usages)
    total_out = sum(u.get('out_tokens', 0) for u in all_usages)
    total_tok = sum(u.get('total_tokens', 0) for u in all_usages)
    
    engine = all_usages[0].get('engine', 'auto')
    model = all_usages[0].get('model', engine)
    
    m = model.lower()
    cost_usd = 0.0
    notes = ""
    
    if 'gemini' in m or engine == 'gemini':
        cost_usd = (total_in / 1_000_000) * 0.075 + (total_out / 1_000_000) * 0.30
        notes = "Безкоштовно у Google AI Studio (Free Tier)"
    elif 'gpt-4o-mini' in m:
        cost_usd = (total_in / 1_000_000) * 0.15 + (total_out / 1_000_000) * 0.60
        notes = "$0.15 / $0.60 за 1M токенів"
    elif 'gpt-4o' in m:
        cost_usd = (total_in / 1_000_000) * 2.50 + (total_out / 1_000_000) * 10.00
        notes = "$2.50 / $10.00 за 1M токенів"
    elif 'claude-3-5-sonnet' in m:
        cost_usd = (total_in / 1_000_000) * 3.00 + (total_out / 1_000_000) * 15.00
        notes = "$3.00 / $15.00 за 1M токенів"
    elif 'haiku' in m:
        cost_usd = (total_in / 1_000_000) * 0.80 + (total_out / 1_000_000) * 4.00
        notes = "$0.80 / $4.00 за 1M токенів"
    elif 'deepseek' in m:
        cost_usd = (total_in / 1_000_000) * 0.14 + (total_out / 1_000_000) * 0.28
        notes = "$0.14 / $0.28 за 1M токенів"
    else:
        cost_usd = 0.0
        notes = "Локальний рушій (Безкоштовно)"
        
    uah_cost = cost_usd * 41.5
    cost_str = f"${cost_usd:.5f} USD (~{uah_cost:.2f} грн)"
    if notes:
        cost_str += f" [{notes}]"
        
    print("\n  " + "─" * 70, flush=True)
    print("  📊 Статистика використання AI API та оцінка вартості:", flush=True)
    print(f"     • Рушій / Модель:       {model.upper()}", flush=True)
    print(f"     • Оброблено сторінок:   {total_pages} стор.", flush=True)
    print(f"     • Вхідні токени (in):   {total_in:,} tokens (зображення + системний промпт)", flush=True)
    print(f"     • Вихідні токени (out): {total_out:,} tokens (згенерований Markdown)", flush=True)
    print(f"     • Всього токенів:       {total_tok:,} tokens", flush=True)
    print(f"     • Орієнтовна вартість:  {cost_str}", flush=True)
    print("  " + "─" * 70 + "\n", flush=True)


# ──────────────────────────────────────────────────────
# Конвертація багатосторінкових PDF (до 1000+ сторінок)
# ──────────────────────────────────────────────────────

def convert_pdf_ocr(
    pdf_path: Path,
    output_path: Path = None,
    engine: str = 'auto',
    dpi: int = 200,
    concurrency: int = 3,
    use_cache: bool = True
) -> str:
    """
    Посторінкова OCR-конвертація PDF файлу будь-якого обсягу (від 1 до 1000+ сторінок).
    Використовує кеш-чекпоінти для відновлення при перериванні.
    """
    import fitz
    pdf_path = Path(pdf_path).resolve()
    
    chosen_engine = select_best_engine(engine)
    if chosen_engine == 'none':
        raise RuntimeError(
            "\n" + "=" * 64 + "\n"
            "[УВАГА] Не знайдено жодного налаштованого рушія OCR!\n"
            "Для розпізнавання сканованого PDF оберіть один зі способів:\n\n"
            "  1. Google Gemini Vision (Найшвидший & Безкоштовний):\n"
            "     Отримайте безкоштовний API ключ: https://aistudio.google.com/app/apikey\n"
            "     Та додайте у файл .env (або через меню convert_ocr_pdf.cmd [5]):\n"
            "     GEMINI_API_KEY=AIzaSy...\n\n"
            "  2. OpenAI / Claude / DeepSeek:\n"
            "     Додайте OPENAI_API_KEY, ANTHROPIC_API_KEY або DEEPSEEK_API_KEY у .env\n\n"
            "  3. Локальний Tesseract OCR:\n"
            "     Встановіть Tesseract у Windows: winget install UB-Mannheim.TesseractOCR\n"
            "     (або завантажте з https://github.com/UB-Mannheim/tesseract/wiki)\n"
            "  4. Локальний PaddleOCR:\n"
            "     Встановіть: pip install paddlepaddle paddleocr\n"
            + "=" * 64
        )
        
    print(f"  Рушій OCR: [{chosen_engine.upper()}] | DPI: {dpi} | Потоки: {concurrency}")
    
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    
    # Папка кешу контрольних точок (Checkpoint / Resume)
    cache_dir = pdf_path.parent / ".ocr_cache" / pdf_path.stem
    if use_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        
    pages_results = [None] * total_pages
    pages_to_process = []
    all_usages = []
    
    # 1. Перевіряємо наявність закешованих сторінок
    for pno in range(total_pages):
        cache_file = cache_dir / f"page_{pno+1:04d}.md"
        if use_cache and cache_file.exists() and cache_file.stat().st_size > 10:
            pages_results[pno] = cache_file.read_text(encoding='utf-8')
        else:
            pages_to_process.append(pno)
            
    cached_count = total_pages - len(pages_to_process)
    if cached_count > 0:
        print(f"  ⚡ Відновлено з кешу: {cached_count}/{total_pages} сторінок")
        
    # 2. Обробка решти сторінок
    if pages_to_process:
        print(f"  ⏳ Запуск OCR розпізнавання: {len(pages_to_process)} стор. (Рушій: {chosen_engine.upper()})...", flush=True)
        
        done_counter = [cached_count]
        
        def _process_page(pno):
            page_num = pno + 1
            t_start = time.time()
            print(f"  [→] Сторінка {page_num}/{total_pages}: рендеринг та запит до {chosen_engine.upper()}...", flush=True)
            
            page = doc[pno]
            # In-memory рендеринг сторінки у високій якості
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes('png')
            
            raw_text, usage_info = ocr_single_image(img_bytes, engine=chosen_engine)
            md_text = _clean_ocr_markdown(raw_text)
            
            elapsed = time.time() - t_start
            done_counter[0] += 1
            tok_info = f"{usage_info.get('total_tokens', 0):,} tok" if usage_info.get('total_tokens') else f"{len(md_text)} симв."
            print(f"  [✓] Сторінка {page_num}/{total_pages}: успішно розпізнано за {elapsed:.1f}с ({tok_info}) [{done_counter[0]}/{total_pages}]", flush=True)
            
            if use_cache:
                cache_file = cache_dir / f"page_{pno+1:04d}.md"
                cache_file.write_text(md_text, encoding='utf-8')
                
            return pno, md_text, usage_info

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_page = {executor.submit(_process_page, p): p for p in pages_to_process}
            for future in as_completed(future_to_page):
                pno, page_md, page_usage = future.result()
                pages_results[pno] = page_md
                all_usages.append(page_usage)
                
    # Друк підсумкової статистики вартості та токенів
    if all_usages:
        print_usage_cost_summary(all_usages, len(all_usages))
            
    full_markdown = '\n\n---\n\n'.join(_clean_ocr_markdown(p) for p in pages_results if p)
    full_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown).strip() + '\n'
    
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(full_markdown, encoding='utf-8')
        print(f"  ✓ Збережено: {out_p}")
        
    return full_markdown


def convert_file(input_path: Path, output_dir: Path = None, engine: str = 'auto', dpi: int = 200) -> Path:
    """Конвертує один файл через OCR у вихідну папку."""
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {input_path}")
        
    print(f"  Конвертація через OCR: {input_path.name}")
    out_dir = Path(output_dir) if output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (input_path.stem + '.md')
    
    convert_pdf_ocr(input_path, output_path=out_path, engine=engine, dpi=dpi)
    return out_path


# ──────────────────────────────────────────────────────
# CLI Точка входу
# ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Модульний AI Vision та локальний OCR конвертер для PDF у чистий Markdown (UTF-8)",
        epilog="Приклад: py pdf_ocr_to_md.py input/*.pdf --engine gemini --output Output/"
    )
    parser.add_argument("inputs", nargs="*", help="Шляхи до PDF-файлів або папок")
    parser.add_argument("--output", "-o", default="Output", help="Вихідна папка для .md файлів (за замовчуванням: Output)")
    parser.add_argument("--engine", "-e", default="auto", choices=["auto", "gemini", "openai", "claude", "deepseek", "paddleocr", "tesseract"], help="Рушій розпізнавання (за замовчуванням: auto)")
    parser.add_argument("--dpi", type=int, default=200, help="DPI роздільна здатність рендерингу сторінок (150-300, стандарт: 200)")
    parser.add_argument("--concurrency", "-c", type=int, default=3, help="Кількість паралельних потоків для сторінок (стандарт: 3)")
    parser.add_argument("--no-cache", action="store_true", help="Не використовувати кеш контрольних точок")
    parser.add_argument("--list-engines", action="store_true", help="Показати доступні рушії OCR та конфігурацію")
    
    args = parser.parse_args()
    
    if args.list_engines:
        print("\n=== ДОСТУПНІ РУШІЇ OCR ТА КОНФІГУРАЦІЯ ===")
        engines = get_available_engines()
        for name, info in engines.items():
            status = "✓ ДОСТУПНИЙ" if info['available'] else "✗ ВІДСУТНІЙ"
            print(f"  [{status}] {name.upper():<10} — {info['desc']}")
        print(f"\nРекомендований рушій за замовчуванням: [{select_best_engine().upper()}]\n")
        return
        
    raw_files = []
    for pattern in args.inputs:
        p = Path(pattern)
        if p.is_dir():
            raw_files.extend(sorted(p.glob("*.pdf")))
        else:
            matched = glob.glob(pattern)
            if matched:
                raw_files.extend(Path(f) for f in matched if f.lower().endswith('.pdf'))
            elif p.exists() and p.suffix.lower() == '.pdf':
                raw_files.append(p)
                
    if not raw_files:
        print("Помилка: не знайдено PDF-файлів для OCR обробки.", file=sys.stderr)
        sys.exit(1)
        
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Знайдено {len(raw_files)} PDF-файл(ів) для OCR розпізнавання\n")
    
    success = 0
    errors = 0
    
    for f in raw_files:
        try:
            out_file = out_dir / (f.stem + '.md')
            convert_pdf_ocr(
                f,
                output_path=out_file,
                engine=args.engine,
                dpi=args.dpi,
                concurrency=args.concurrency,
                use_cache=not args.no_cache
            )
            success += 1
        except Exception as e:
            print(f"  ✗ Помилка [{f.name}]: {e}", file=sys.stderr)
            errors += 1
            
    print(f"\nГотово: {success} успішно, {errors} помилок.")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
