# PDF-to-Markdown & AI Vision OCR Subsystem

> **High-fidelity conversion and multimodal AI Vision OCR recognition for Ukrainian official, legislative, and court PDF documents of any volume (from 1 to 1000+ pages) into clean, LLM-optimized UTF-8 Markdown.**
>
> 🇺🇦 **Високоточна обробка, геометрична конвертація та багаторушійне AI Vision OCR розпізнавання офіційних, законодавчих та судових PDF-документів будь-якого обсягу (від 1 до 1000+ сторінок) у чистий, структурований Markdown (UTF-8), оптимізований для систем штучного інтелекту, LLM (Gemini, GPT-4o, Claude) та RAG-пайплайнів.**

---

## Table of Contents / Зміст
- [Overview / Загальний огляд](#overview--загальний-огляд)
- [Key Features / Основні можливості](#key-features--основні-можливості)
- [Component Architecture / Архітектура компонентів](#component-architecture--архітектура-компонентів)
- [Supported OCR & Vision Engines / Підтримувані рушії](#supported-ocr--vision-engines--підтримувані-рушії)
- [Setup & Installation / Налаштування та встановлення](#setup--installation--налаштування-та-встановлення)
  - [1. API Keys Configuration / Налаштування API-ключів](#1-api-keys-configuration--налаштування-api-ключів)
  - [2. Local OCR Engines (Optional) / Локальні рушії](#2-local-ocr-engines-optional--локальні-рушії)
- [Usage Guide / Інструкція з використання](#usage-guide--інструкція-з-використання)
  - [1. Windows Interactive Launcher & Drag-and-Drop (`convert_ocr_pdf.cmd`)](#1-windows-interactive-launcher--drag-and-drop-convert_ocr_pdfcmd)
  - [2. Command Line Interface (CLI) / Командний рядок](#2-command-line-interface-cli--командний-рядок)
  - [3. Python API Integration](#3-python-api-integration)
- [Large Documents & Resiliency (1000+ Pages) / Робота з великими файлами](#large-documents--resiliency-1000-pages--робота-з-великими-файлами)
- [Token & API Cost Monitoring / Моніторинг токенів та вартості](#token--api-cost-monitoring--моніторинг-токенів-та-вартості)
- [Clean Markdown Guarantee / Гарантія чистого Markdown](#clean-markdown-guarantee--гарантія-чистого-markdown)
- [License / Ліцензія](#license--ліцензія)

---

## Overview / Загальний огляд

Official legal, judicial, and state documents in Ukraine are distributed in two distinct PDF formats:
1. **Digital / Native Vector PDFs**: Contain selectable text streams, font mappings, and vector lines.
2. **Scanned / Raster PDFs**: Contain raw scanned images (often low-resolution, tilted, with official stamps, coat of arms, seal marks, or handwriting) without a text layer.

Standard converters often fail by corrupting Cyrillic encodings, losing two-column signature layouts, or crashing on large multi-hundred-page archives. This subsystem delivers a zero-loss, dual-path pipeline: fast geometric extraction for digital pages and state-of-the-art AI Vision recognition for scanned pages.

> 🇺🇦 **Офіційні законодавчі, судові та діловодні документи в Україні поширюються у двох принципово різних форматах PDF:**
> 1. **Цифрові PDF**: містять внутрішній текстовий шар, шрифтові карти та векторні лінії, які виділяються мишкою.
> 2. **Скановані PDF**: містять растрові фотокопії та скани сторінок (часто зі штампами, печатками `М. П.`, гербами та рукописними резолюціями) без цифрового тексту.
>
> **Звичайні утиліти часто спотворюють кириличні символи, ламають двоколонкові підписи або зависають на великих багатосторінкових справах. Цей модуль забезпечує бездоганну обробку: надшвидку геометричну екстракцію для цифрового тексту та передовий AI Vision OCR для сканів.**

---

## Key Features / Основні можливості

- **⚡ Smart Document Auto-Detection**: Automatically analyzes character density ($>50$ chars/page vs. raster area) to choose the optimal processing method.
- **📐 Layout-Aware Native Extraction (`pdf_to_md.py`)**: Preserves visual reading order, `**bold**`/`*italic*` styles, Coat of Arms `[Герб України]`, divider lines `---`, and side-by-side signature blocks (50–200 pages/sec).
- **🧠 Multi-Engine AI Vision & Local OCR (`pdf_ocr_to_md.py`)**: Connects to Google Gemini Vision, OpenAI GPT-4o, Anthropic Claude, DeepSeek, PaddleOCR, and Tesseract.
- **📚 Extreme Scalability (1 to 1000+ Pages)**:
  - **In-Memory Page Rendering**: Renders pages on-the-fly without saving temporary image files to disk.
  - **Checkpoint / Resume Mechanism**: Caches individual recognized pages in `.ocr_cache/` so interrupted jobs resume instantly without re-processing or re-paying.
  - **Multi-Threading & Rate Limiting**: Parallel page dispatching with automatic RPM throttling.
- **📊 Token Usage & API Cost Calculator**: Automatically tracks prompt and completion tokens with live USD and UAH cost calculations.
- **🖱️ Windows Explorer Drag & Drop**: Simply drop any PDF onto `convert_ocr_pdf.cmd` for instant conversion.

> 🇺🇦 **Основні переваги:**
> - **⚡ Розумна авто-детекція**: аналізує щільність тексту та площу зображень для вибору найкращого методу.
> - **📐 Геометрична конвертація (`pdf_to_md.py`)**: збереження порядку читання, жирного/курсивного накреслення, гербів `[Герб України]`, ліній `---` та підписів без виклику нейромереж (50-200 стор./сек).
> - **🧠 Багаторушійний AI Vision & OCR (`pdf_ocr_to_md.py`)**: підтримка Gemini, OpenAI, Claude, DeepSeek, PaddleOCR та Tesseract.
> - **📚 Масштабованість (до 1000+ сторінок)**: посторінковий рендеринг у пам'яті, збереження контрольних точок у `.ocr_cache/` та багатопотоковість.
> - **📊 Автоматичний підрахунок токенів та вартості API**: виводить орієнтовну ціну в USD та грн.
> - **🖱️ Інтеграція з Windows**: підтримка перетягування файлів (Drag & Drop) на `convert_ocr_pdf.cmd`.

---

## Component Architecture / Архітектура компонентів

```text
├── pdf_to_md.py        # Native PDF converter + text density analyzer
├── pdf_ocr_to_md.py    # Multi-engine AI Vision & Local OCR converter
├── convert_ocr_pdf.cmd # Interactive Windows batch CLI with Drag & Drop
└── ocr_readme.md       # Bilingual documentation & user guide
```

---

## Supported OCR & Vision Engines / Підтримувані рушії

```text
┌──────────────────────┬─────────────────────────────────────────────────────┐
│ Рушій / Engine       │ Особливості та конфігурація / Features & Config     │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ Google Gemini Vision │ [ТОП] 15 RPM Free, найвища якість для України       │
│ (gemini-3.6-flash)   │ Конфіг: GEMINI_API_KEY=AIzaSy...                    │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ OpenAI Vision        │ Еталонний Markdown та вилучення складних таблиць    │
│ (gpt-4o / mini)      │ Конфіг: OPENAI_API_KEY=sk-...                       │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ Anthropic Claude     │ Точне відтворення ієрархії статей та юр. контексту  │
│ (claude-3-5-sonnet)  │ Конфіг: ANTHROPIC_API_KEY=sk-ant-...                │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ DeepSeek / Custom    │ Сумісний з будь-яким OpenAI endpoint (vLLM/Ollama)  │
│ (deepseek-chat)      │ Конфіг: DEEPSEEK_API_KEY=sk-..., OPENAI_BASE_URL=.. │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ PaddleOCR (Локально) │ Нейро-рушій для кирилиці та таблиць (PP-Structure)  │
│ (PaddlePaddle)       │ Встановлення: pip install paddlepaddle paddleocr    │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ Tesseract OCR        │ C++ офлайн-рушій з мовними пакетами ukr + eng       │
│ (tesseract-ocr)      │ Встановлення: winget install UB-Mannheim.Tesseract  │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ MarkItDown OCR       │ Vision OCR плагін для Microsoft MarkItDown          │
│ (microsoft)          │ Встановлення: pip install markitdown-ocr            │
└──────────────────────┴─────────────────────────────────────────────────────┘
```

---

## Setup & Installation / Налаштування та встановлення

### 1. API Keys Configuration / Налаштування API-ключів

Create a `.env` file in the project root directory (or configure keys interactively via menu option `[5]` in `convert_ocr_pdf.cmd`):

> 🇺🇦 Створіть файл `.env` у кореневій папці проєкту (або налаштуйте ключі через пункт меню `[5]` у `convert_ocr_pdf.cmd`):

```env
# 🌟 Google Gemini (Recommended: Free tier available at https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=AIzaSy...

# OpenAI (GPT-4o / GPT-4o-mini)
OPENAI_API_KEY=sk-...

# Anthropic Claude (Claude 3.5 Sonnet / Haiku)
ANTHROPIC_API_KEY=sk-ant-...

# DeepSeek / Custom OpenAI Endpoint (e.g. Local vLLM or Ollama)
DEEPSEEK_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com
```

### 2. Local OCR Engines (Optional) / Локальні рушії

For 100% offline OCR without internet connectivity:

> 🇺🇦 Для повністю автономного розпізнавання без доступу до Інтернету:

* **Tesseract OCR (Windows)**:
  ```powershell
  winget install UB-Mannheim.TesseractOCR
  ```
* **PaddleOCR (Neural Engine)**:
  ```bash
  pip install paddlepaddle paddleocr
  ```

---

## Usage Guide / Інструкція з використання

### 1. Windows Interactive Launcher & Drag-and-Drop (`convert_ocr_pdf.cmd`)

1. **Instant Drag & Drop**: Drag any `.pdf` file directly onto `convert_ocr_pdf.cmd` in Windows Explorer.
2. **Interactive Menu**: Double-click `convert_ocr_pdf.cmd`:

```text
================================================================
        КОНВЕРТЕР ТА OCR РОЗПІЗНАВАННЯ PDF У MARKDOWN
================================================================

 [1] Розумна авто-конвертація (Цифровий -> Текст, Скан -> AI OCR)
 [2] Пакетна авто-конвертація всіх .pdf з папки "input"
 [3] Швидка пряма конвертація цифрових PDF (без OCR)
 [4] Примусове OCR розпізнавання (Gemini / OpenAI / Claude / Tesseract)
 [5] Перевірити статус рушіїв OCR та налаштувати API-ключі
 [6] Вказати власні папки (Вхідна тека -> Вихідна тека)
 [7] Відкрити папку результатів (Output)
 [0] Вихід

 (Підказка: ви також можете просто перетягнути будь-який PDF сюди!)
================================================================
```

---

### 2. Command Line Interface (CLI) / Командний рядок

#### Check text density / Перевірка типу документа:
```bash
py pdf_to_md.py input/ --check-only
```

#### Native conversion with auto-OCR fallback / Пряма конвертація з авто-детекцією:
```bash
# Single file / Окремий файл
py pdf_to_md.py "input/document.pdf" --output Output/ --auto-ocr

# Batch directory / Уся папка
py pdf_to_md.py input/ --output Output/ --auto-ocr
```

#### OCR recognition via specific engine / Запуск через конкретний рушій:
```bash
# List available engines / Список доступних рушіїв
py pdf_ocr_to_md.py --list-engines

# Google Gemini Vision
py pdf_ocr_to_md.py "input/scan.pdf" --engine gemini --output Output/

# OpenAI GPT-4o Vision
py pdf_ocr_to_md.py "input/scan.pdf" --engine openai --output Output/

# Local Tesseract OCR
py pdf_ocr_to_md.py "input/scan.pdf" --engine tesseract --output Output/

# 1000-page document with 5 parallel threads / Багатопотокова обробка
py pdf_ocr_to_md.py "input/huge_archive.pdf" --engine gemini --concurrency 5 --dpi 200
```

---

### 3. Python API Integration

```python
from pathlib import Path
from pdf_to_md import convert_pdf_file, detect_pdf_text_density
from pdf_ocr_to_md import convert_pdf_ocr

pdf_path = Path("input/sample.pdf")

# 1. Analyze document type
density = detect_pdf_text_density(pdf_path)
print(f"Is Scanned: {density['is_scanned']}, Chars/page: {density['avg_chars_per_page']}")

# 2. Convert natively or run OCR
if not density['is_scanned']:
    md = convert_pdf_file(pdf_path, output_path="Output/sample.md")
else:
    md = convert_pdf_ocr(pdf_path, output_path="Output/sample.md", engine="gemini")
```

---

## Large Documents & Resiliency (1000+ Pages) / Робота з великими файлами

When processing multi-hundred-page archives (e.g. 50 to 1000+ pages), the system saves intermediate page results into `.ocr_cache/<file_stem>/page_NNNN.md`:
* **Crash Resilience**: If network drops or rate limits occur, re-running the command immediately resumes from the exact interrupted page without re-rendering or incurring API charges for already finished pages.
* **Cache Bypass**: Use `--no-cache` to force a fresh re-scan.

> 🇺🇦 **Надійність при обробці великих документів:**
> Кожна сторінка автоматично зберігається у `.ocr_cache/<назва>/page_NNNN.md`. При збої мережі чи перевищенні лімітів повторний запуск **миттєво продовжує роботу з місця зупинки**.

---

## Token & API Cost Monitoring / Моніторинг токенів та вартості

When AI Vision models are used, the subsystem automatically computes token metrics and calculates approximate USD/UAH costs upon completion:

> 🇺🇦 При використанні AI Vision моделей система автоматично підраховує токени та розраховує орієнтовну вартість:

```text
  ──────────────────────────────────────────────────────────────────────
  📊 Статистика використання AI API та оцінка вартості:
     • Рушій / Модель:       GEMINI-3.6-FLASH
     • Оброблено сторінок:   1 стор.
     • Вхідні токени (in):   1,554 tokens (зображення + системний промпт)
     • Вихідні токени (out): 699 tokens (згенерований Markdown)
     • Всього токенів:       2,253 tokens
     • Орієнтовна вартість:  $0.00033 USD (~0.01 грн) [Безкоштовно у Google AI Studio (Free Tier)]
  ──────────────────────────────────────────────────────────────────────
```

---

## Clean Markdown Guarantee / Гарантія чистого Markdown

The output post-processor automatically cleans AI hallucinations and extraneous HTML artifacts:
* Strips all raw HTML formatting tags (`<u>`, `<span>`, `<font>`, `<br>`).
* Removes code block wrappers (````markdown ```).
* Normalizes whitespace and header levels for flawless indexing in RAG vector databases.

> 🇺🇦 **100% чистий Markdown**: повністю очищено від небажаних HTML-тегів (`<u>`, `<font>`), виправлено пробіли та підготовлено для векторних баз RAG.

---

## License / Ліцензія

This subsystem is part of the Law-to-Markdown project and is licensed under the **MIT License**.
* **Author**: Paul Gorinetsky 
