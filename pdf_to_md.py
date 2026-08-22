#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_to_md.py — Високоточний геометричний конвертер цифрових PDF у чистий Markdown (UTF-8).
Оптимізований для законів, наказів, постанов, судових рішень та офіційних документів України.

Особливості:
- Точне геометричне впорядкування слів і рядків (Reading Order) без злипання та перемішування.
- Збереження стилів шрифтів (**жирний**, *курсив*) та правильне винесення розділових знаків.
- Розпізнавання Герба України, логотипів, векторних ліній розділювачів та двоколонкових підписів/адрес.
- Автоматична детекція сканованих/растрових документів із можливістю перенаправлення на OCR (pdf_ocr_to_md.py).
- Ефективна потокова обробка для великих документів (до 1000+ сторінок).
"""

import sys
import os
import re
import glob
import argparse
import unicodedata
from pathlib import Path

# Встановлюємо UTF-8 для виводу в консоль
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


def _safe_unspace(text: str) -> str:
    """Виправляє розряджений текст 'З А К О Н' -> 'ЗАКОН', зберігаючи звичайні слова."""
    if not text:
        return text
    def _repl_upper(m):
        raw = m.group(0)
        return re.sub(r'\s+', '', raw)
    text = re.sub(r'\b(?:[А-ЯA-ZІЇЄҐ]\s+){2,}[А-ЯA-ZІЇЄҐ]\b', _repl_upper, text)
    known_spaced = [
        ('п о с т а н о в л я є', 'постановляє'),
        ('П О С Т А Н О В Л Я Є', 'ПОСТАНОВЛЯЄ'),
        ('н а к а з у ю', 'НАКАЗУЮ'),
        ('Н А К А З У Ю', 'НАКАЗУЮ'),
        ('з а т в е р д ж е н о', 'затверджено'),
        ('З А Т В Е Р Д Ж Е Н О', 'ЗАТВЕРДЖЕНО'),
        ('р о з п о р я д ж е н н я', 'розпорядження'),
        ('Р О З П О Р Я Д Ж Е Н Н Я', 'РОЗПОРЯДЖЕННЯ'),
    ]
    for spaced, fixed in known_spaced:
        text = re.sub(re.escape(spaced), fixed, text, flags=re.IGNORECASE)
    return text


def _clean_markdown_inline(text: str) -> str:
    """Об'єднує сусідні жирні/курсивні маркери та виправляє пробіли."""
    if not text:
        return ''
    # Об'єднуємо **слово1** **слово2** -> **слово1 слово2**
    while re.search(r'\*\*(.+?)\*\*\s+\*\*(.+?)\*\*', text):
        text = re.sub(r'\*\*(.+?)\*\*\s+\*\*(.+?)\*\*', r'**\1 \2**', text)
    # Об'єднуємо *слово1* *слово2* -> *слово1 слово2*
    while re.search(r'(?<!\*)\*(.+?)\*(?!\*)\s+(?<!\*)\*(.+?)\*(?!\*)', text):
        text = re.sub(r'(?<!\*)\*(.+?)\*(?!\*)\s+(?<!\*)\*(.+?)\*(?!\*)', r'*\1 \2*', text)
    # Пунктуація після жирного/курсиву
    text = re.sub(r'\s+([,\.;:])', r'\1', text)
    return re.sub(r'[ \t]{2,}', ' ', text).strip()


def _format_pdf_spans(spans: list) -> str:
    """Форматує список спанів одного рядка у валідний Markdown рядок."""
    formatted = []
    for s in spans:
        text = s.get('text', '')
        if not text or not text.strip():
            continue
        core = text.strip()
        
        # Відокремлюємо кінцеву пунктуацію: "України," -> core "України", punct ","
        m_p = re.match(r'^(.*?)([,\.;:]+)$', core)
        punct = ''
        if m_p and m_p.group(1):
            core = m_p.group(1)
            punct = m_p.group(2)
            
        if s.get('bold'):
            formatted.append(f'**{core}**{punct}')
        elif s.get('italic'):
            formatted.append(f'*{core}*{punct}')
        else:
            formatted.append(f'{core}{punct}')
            
    line = ' '.join(formatted)
    return _clean_markdown_inline(line)


def detect_pdf_text_density(pdf_path: Path, max_sample_pages: int = 10) -> dict:
    """
    Аналізує PDF на наявність цифрового тексту vs сканованих зображень.
    Повертає словник зі статистикою та вердиктом: is_scanned, is_digital, is_mixed.
    """
    try:
        import fitz
    except ImportError:
        return {'is_digital': True, 'is_scanned': False, 'total_pages': 1, 'avg_chars_per_page': 500}

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    sample_pages = min(total_pages, max_sample_pages)
    
    char_counts = []
    image_counts = []
    
    for i in range(sample_pages):
        page = doc[i]
        text = page.get_text().strip()
        char_counts.append(len(text))
        images = page.get_images()
        image_counts.append(len(images))
        
    avg_chars = sum(char_counts) / max(sample_pages, 1)
    pages_with_low_text = sum(1 for c in char_counts if c < 50)
    has_images = sum(image_counts) > 0
    
    is_scanned = (avg_chars < 50 and has_images) or (pages_with_low_text == sample_pages and has_images)
    is_mixed = (pages_with_low_text > 0 and pages_with_low_text < sample_pages)
    is_digital = not is_scanned
    
    return {
        'total_pages': total_pages,
        'sampled_pages': sample_pages,
        'avg_chars_per_page': avg_chars,
        'pages_with_low_text': pages_with_low_text,
        'is_digital': is_digital,
        'is_scanned': is_scanned,
        'is_mixed': is_mixed
    }


def convert_pdf_page_to_md(page, page_num: int, total_pages: int) -> str:
    """Конвертує одну сторінку PDF у структурований Markdown."""
    page_width = page.rect.width
    page_height = page.rect.height
    elements = []
    
    # 1. Зображення (Герб України / логотипи / печатки)
    for img_info in page.get_images():
        xref = img_info[0]
        for rect in page.get_image_rects(xref):
            # Герб України зазвичай у верхній центральній частині
            if rect.y0 < page_height * 0.25 and abs((rect.x0 + rect.x1) / 2 - page_width / 2) < page_width * 0.25:
                elements.append((rect.y0, rect.x0, rect.y1, rect.x1, 'img', '[Герб України]'))
            else:
                elements.append((rect.y0, rect.x0, rect.y1, rect.x1, 'img', '[Зображення]'))
                
    # 2. Векторні лінії (роздільники / горизонтальні риски)
    for d in page.get_drawings():
        r = d.get('rect')
        if r and r.width > page_width * 0.4 and r.height <= 3:
            elements.append((r.y0, r.x0, r.y1, r.x1, 'hr', '---'))
            
    # 3. Текстові фрагменти (spans)
    text_dict = page.get_text('dict')
    for block in text_dict.get('blocks', []):
        if block.get('type') == 0:  # text
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    text = span.get('text', '')
                    if not text or not text.strip():
                        continue
                    x0, y0, x1, y1 = span.get('bbox')
                    flags = span.get('flags', 0)
                    font = span.get('font', '').lower()
                    size = span.get('size', 10)
                    
                    is_bold = bool(flags & (1 << 4)) or any(k in font for k in ('bold', 'black', 'heavy', 'semibold'))
                    is_italic = bool(flags & (1 << 1)) or any(k in font for k in ('italic', 'oblique'))
                    
                    elements.append((y0, x0, y1, x1, 'span', {
                        'text': text,
                        'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                        'bold': is_bold, 'italic': is_italic, 'size': size
                    }))

    elements.sort(key=lambda el: (round(el[0], 1), round(el[1], 1)))
    
    # Групування у візуальні рядки за Y-координатою
    visual_lines = []
    curr_line = []
    curr_y = None
    curr_y1 = None
    
    for el in elements:
        y0, x0, y1, x1, el_type, data = el
        if curr_y is None or abs(y0 - curr_y) > 3.5:
            if curr_line:
                visual_lines.append((curr_y, curr_y1, curr_line))
            curr_line = [(x0, x1, el_type, data)]
            curr_y = y0
            curr_y1 = y1
        else:
            curr_line.append((x0, x1, el_type, data))
            if y1 > curr_y1:
                curr_y1 = y1
            
    if curr_line:
        visual_lines.append((curr_y, curr_y1, curr_line))
        
    rendered_blocks = []
    
    for y0, y1, line_items in visual_lines:
        line_items.sort(key=lambda item: item[0])
        
        if any(item[2] in ('img', 'hr') for item in line_items):
            for x0, x1, itype, data in line_items:
                if itype in ('img', 'hr'):
                    rendered_blocks.append(('block', data, x0, y0, y1))
            continue
            
        spans = [item[3] for item in line_items if item[2] == 'span']
        if not spans:
            continue
            
        min_x0 = spans[0]['x0']
        
        # Двоколонкові рядки (розрив між фрагментами > 40pt)
        has_gap = False
        gap_idx = -1
        for i in range(len(spans) - 1):
            if spans[i+1]['x0'] - spans[i]['x1'] > 40:
                has_gap = True
                gap_idx = i
                break
                
        if has_gap and gap_idx >= 0:
            left = _format_pdf_spans(spans[:gap_idx+1])
            right = _format_pdf_spans(spans[gap_idx+1:])
            rendered_blocks.append(('col', f'{left:<35} {right}', min_x0, y0, y1))
        else:
            line_str = _format_pdf_spans(spans)
            clean_plain = _safe_unspace(re.sub(r'[\*_\s]+', ' ', line_str)).strip()
            
            # Підкреслення футера або довгі риски
            if re.search(r'_{10,}', line_str) or (len(line_str) >= 10 and not line_str.strip('* _-')):
                rendered_blocks.append(('block', '---', min_x0, y0, y1))
            # Заголовки вищих органів влади
            elif re.match(r'^(?:МІНІСТЕРСТВО|ВЕРХОВНА РАДА|КАБІНЕТ МІНІСТРІВ|ПРЕЗИДЕНТ)\s+[А-ЯІЇЄҐA-Z\s]+$', clean_plain):
                rendered_blocks.append(('block', f'# {clean_plain}', min_x0, y0, y1))
            # Вид нормативного акту
            elif re.match(r'^(?:ЗАКОН УКРАЇНИ|ПОСТАНОВА|НАКАЗ|УКАЗ|РОЗПОРЯДЖЕННЯ|РІШЕННЯ|ДЕКРЕТ)(?:\s+ВЕРХОВНОЇ\s+РАДИ\s+УКРАЇНИ)?$', clean_plain):
                rendered_blocks.append(('block', f'# {clean_plain}', min_x0, y0, y1))
            # Розділи / статті
            elif re.match(r'^(?:Розділ|Глава|Книга|Частина|Стаття)\s+[IVXLCDM\d]+', clean_plain, re.IGNORECASE):
                rendered_blocks.append(('block', f'## {line_str}', min_x0, y0, y1))
            # Відомості ВВР
            elif re.search(r'Відомості\s+Верховної\s+Ради', clean_plain, re.IGNORECASE):
                clean_vvr = line_str.strip(' *()')
                rendered_blocks.append(('block', f'*({clean_vvr})*', min_x0, y0, y1))
            # Зміни
            elif re.match(r'^(?:\{|\()?\s*[\*_]*(?:Із\s+змінами|Наказ\s+втратив|Втратив\s+чинність)', clean_plain, re.IGNORECASE):
                clean_ch = line_str.strip(' *()')
                rendered_blocks.append(('block', f'> *{{{clean_ch}}}*', min_x0, y0, y1))
            else:
                rendered_blocks.append(('line', line_str, min_x0, y0, y1))
                
    # Формування цілісних абзаців
    final_doc_lines = []
    cur_para = []
    prev_y1 = None
    prev_is_right = False
    
    for b_type, text, x0, y0, y1 in rendered_blocks:
        if not text:
            continue
        if b_type in ('block', 'col'):
            if cur_para:
                final_doc_lines.append(_clean_markdown_inline(' '.join(cur_para)))
                cur_para = []
            final_doc_lines.append(text)
            prev_y1 = y1
            prev_is_right = False
        elif b_type == 'line':
            is_subject = bool(re.match(r'^\*[^*].*?[^*]\*$', text))
            is_annex = text.startswith('Додаток:')
            is_number = bool(re.match(r'^\d{2}\.\d{2}\.\d{4}\s+(?:N|№)', text))
            is_right_aligned = x0 > page_width * 0.45
            
            line_gap = (y0 - prev_y1) if prev_y1 is not None else 0
            is_large_gap = line_gap > 10
            
            if is_subject or is_annex or is_number or is_right_aligned or text.startswith('#') or is_large_gap:
                if cur_para:
                    final_doc_lines.append(_clean_markdown_inline(' '.join(cur_para)))
                    cur_para = []
                
                if is_right_aligned:
                    if prev_is_right and line_gap < 8 and final_doc_lines and not final_doc_lines[-1].startswith('#'):
                        final_doc_lines[-1] += '\n' + text
                    else:
                        final_doc_lines.append(text)
                    prev_is_right = True
                else:
                    prev_is_right = False
                    if is_subject or is_annex or is_number or text.startswith('#'):
                        final_doc_lines.append(text)
                    else:
                        cur_para.append(text)
            else:
                prev_is_right = False
                cur_para.append(text)
                if text.endswith(('.', '!', '?', ':')):
                    final_doc_lines.append(_clean_markdown_inline(' '.join(cur_para)))
                    cur_para = []
                    
            prev_y1 = y1
            
    if cur_para:
        final_doc_lines.append(_clean_markdown_inline(' '.join(cur_para)))
        
    return '\n\n'.join(final_doc_lines)


def convert_pdf_to_md(input_path: Path, max_pages: int = None) -> str:
    """
    Головна функція конвертації цифрового PDF у Markdown.
    Підтримує посторінкову потокову обробку для великих файлів (1000+ сторінок).
    """
    try:
        import fitz
    except ImportError:
        try:
            from markitdown import MarkItDown
            return MarkItDown().convert(str(input_path)).text_content
        except Exception as e:
            raise RuntimeError(f"PyMuPDF або MarkItDown не встановлені: {e}")

    doc = fitz.open(str(input_path))
    total_pages = len(doc)
    pages_to_process = min(total_pages, max_pages) if max_pages else total_pages
    
    pages_md = []
    for pno in range(pages_to_process):
        page = doc[pno]
        page_content = convert_pdf_page_to_md(page, pno + 1, total_pages)
        if page_content.strip():
            pages_md.append(page_content.strip())
            
    res = '\n\n---\n\n'.join(pages_md)
    res = re.sub(r'\n{3,}', '\n\n', res)
    return res.strip() + '\n'


def convert_file(input_path: Path, output_dir: Path = None, auto_ocr: bool = False, ocr_engine: str = 'auto') -> Path:
    """Конвертує PDF-файл у Markdown з опціональним OCR перенаправленням."""
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {input_path}")
        
    print(f"  Обробка PDF: {input_path.name}")
    
    # 1. Перевірка наявності цифрового тексту
    density = detect_pdf_text_density(input_path)
    if density['is_scanned']:
        print(f"  ⚠ Виявлено сканований PDF (без цифрового тексту, {density['total_pages']} стор.)")
        if auto_ocr:
            print(f"  ⚡ Запуск OCR-розпізнавання (рушій: {ocr_engine})...")
            try:
                import pdf_ocr_to_md
                return pdf_ocr_to_md.convert_file(input_path, output_dir=output_dir, engine=ocr_engine)
            except ImportError:
                print("  [!] Модуль pdf_ocr_to_md.py не знайдено, продовжую пряму конвертацію.")
        else:
            print("  ℹ Рекомендація: запустіть OCR через pdf_ocr_to_md.py або використовуйте прапорець --auto-ocr")
            
    # 2. Пряма геометрична конвертація
    md_text = convert_pdf_to_md(input_path)
    out_dir = Path(output_dir) if output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (input_path.stem + '.md')
    out_path.write_text(md_text, encoding='utf-8')
    print(f"  ✓ Збережено: {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Високоточний геометричний конвертер цифрових PDF у чистий Markdown (UTF-8)",
        epilog="Приклад: py pdf_to_md.py input/*.pdf --output Output/ --auto-ocr"
    )
    parser.add_argument("inputs", nargs="*", help="Шляхи до PDF-файлів або папок")
    parser.add_argument("--output", "-o", default="Output", help="Вихідна папка для .md файлів (за замовчуванням: Output)")
    parser.add_argument("--auto-ocr", action="store_true", help="Автоматично запускати OCR для сканованих документів")
    parser.add_argument("--ocr-engine", default="auto", choices=["auto", "gemini", "openai", "claude", "deepseek", "paddleocr", "tesseract"], help="Рушій OCR при перенаправленні")
    parser.add_argument("--check-only", action="store_true", help="Тільки перевірити щільність тексту (скан чи цифровий) без конвертації")
    parser.add_argument("--max-pages", type=int, default=None, help="Обмежити кількість сторінок для обробки")
    
    args = parser.parse_args()
    
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
        print("Помилка: не знайдено PDF-файлів для обробки.", file=sys.stderr)
        sys.exit(1)
        
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Знайдено {len(raw_files)} PDF-файл(ів) для обробки\n")
    
    success = 0
    errors = 0
    
    for f in raw_files:
        try:
            if args.check_only:
                density = detect_pdf_text_density(f)
                status = "СКАН (потрібен OCR)" if density['is_scanned'] else ("ЗМІШАНИЙ" if density['is_mixed'] else "ЦИФРОВИЙ (OK)")
                print(f"  [{status}] {f.name} ({density['total_pages']} стор., ~{int(density['avg_chars_per_page'])} симв./стор.)")
            else:
                convert_file(f, output_dir=out_dir, auto_ocr=args.auto_ocr, ocr_engine=args.ocr_engine)
            success += 1
        except Exception as e:
            print(f"  ✗ Помилка [{f.name}]: {e}", file=sys.stderr)
            errors += 1
            
    print(f"\nГотово: {success} успішно, {errors} помилок.")
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
