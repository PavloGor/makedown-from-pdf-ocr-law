@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

REM ── Якщо передано аргументи при запуску (Drag and Drop на файл) ──
if not "%~1"=="" goto DRAG_DROP

REM ── Пошук Python ──
set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>&1 && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ================================================================
    echo [ПОМИЛКА] Python не знайдено в системі! Встановіть Python 3.
    echo ================================================================
    pause
    exit /b 1
)

if not exist "%~dp0Output" mkdir "%~dp0Output"
if not exist "%~dp0input" mkdir "%~dp0input"

REM ── Інтерактивне меню ──
:MENU
cls
echo ================================================================
echo         КОНВЕРТЕР ТА OCR РОЗПІЗНАВАННЯ PDF У MARKDOWN
echo ================================================================
echo.
echo  [1] Розумна авто-конвертація ^(Цифровий -^> Текст, Скан -^> AI OCR^)
echo  [2] Пакетна авто-конвертація всіх .pdf з папки "input"
echo  [3] Швидка пряма конвертація цифрових PDF ^(без OCR^)
echo  [4] Примусове OCR розпізнавання ^(Gemini / Mistral / OpenAI / Claude^)
echo  [5] Перевірити статус рушіїв OCR та налаштувати API-ключі
echo  [6] Вказати власні папки ^(Вхідна тека -^> Вихідна тека^)
echo  [7] Відкрити папку результатів ^(Output^)
echo  [0] Вихід
echo.
echo  ^(Підказка: ви також можете просто перетягнути будь-який PDF сюди!^)
echo ================================================================
set "CHOICE="
set /p "CHOICE=Оберіть варіант [0-7] або перетягніть файл: "

if not defined CHOICE goto MENU

set "CLEAN_CHOICE=!CHOICE:"=!"

:TRIM_CHOICE_LOOP
if "!CLEAN_CHOICE:~-1!"==" " (
    set "CLEAN_CHOICE=!CLEAN_CHOICE:~0,-1!"
    goto TRIM_CHOICE_LOOP
)

if exist "!CLEAN_CHOICE!" (
    set "FILE_PATH=!CLEAN_CHOICE!"
    goto RUN_SMART_CONVERT_FILE
)

if "!CLEAN_CHOICE!"=="1" goto SMART_SINGLE_FILE
if "!CLEAN_CHOICE!"=="2" goto BULK_AUTO_INPUT
if "!CLEAN_CHOICE!"=="3" goto FAST_DIRECT_CONVERT
if "!CLEAN_CHOICE!"=="4" goto FORCE_OCR_MENU
if "!CLEAN_CHOICE!"=="5" goto CONFIGURE_KEYS
if "!CLEAN_CHOICE!"=="6" goto CUSTOM_DIRS
if "!CLEAN_CHOICE!"=="7" goto OPEN_OUTPUT
if "!CLEAN_CHOICE!"=="0" goto EXIT_APP

echo.
echo [!] Невірний вибір: "!CHOICE!". Спробуйте ще раз.
timeout /t 2 >nul
goto MENU


REM ── 1. Розумна конвертація окремого файлу ──
:SMART_SINGLE_FILE
echo.
echo ----------------------------------------------------------------
echo  Розумна авто-конвертація окремого PDF файлу
echo ----------------------------------------------------------------
set "FILE_PATH="
set /p "FILE_PATH=Перетягніть PDF файл у це вікно або введіть шлях: "
if not defined FILE_PATH (
    echo [Скасовано] Шлях не вказано.
    echo.
    pause
    goto MENU
)

set "FILE_PATH=!FILE_PATH:"=!"

:TRIM_FILE_LOOP
if "!FILE_PATH:~-1!"==" " (
    set "FILE_PATH=!FILE_PATH:~0,-1!"
    goto TRIM_FILE_LOOP
)

:RUN_SMART_CONVERT_FILE
if not exist "!FILE_PATH!" (
    echo.
    echo [ПОМИЛКА] Файл не знайдено: "!FILE_PATH!"
    echo.
    pause
    goto MENU
)

echo.
echo ----------------------------------------------------------------
echo  Конвертую: "!FILE_PATH!"
echo ----------------------------------------------------------------
"!PYTHON_CMD!" "%~dp0pdf_to_md.py" "!FILE_PATH!" --output "%~dp0Output" --auto-ocr
echo.
pause
goto MENU


REM ── 2. Пакетна авто-конвертація з папки input ──
:BULK_AUTO_INPUT
echo.
echo ----------------------------------------------------------------
echo  Пакетна авто-конвертація всіх PDF файлів з папки "input"...
echo ----------------------------------------------------------------
"!PYTHON_CMD!" "%~dp0pdf_to_md.py" "%~dp0input" --output "%~dp0Output" --auto-ocr
echo.
pause
goto MENU


REM ── 3. Швидка пряма конвертація без OCR ──
:FAST_DIRECT_CONVERT
echo.
echo ----------------------------------------------------------------
echo  Швидка пряма геометрична конвертація цифрових PDF ^(без OCR^)
echo ----------------------------------------------------------------
set "FAST_PATH="
set /p "FAST_PATH=Перетягніть PDF або натисніть Enter для папки 'input': "
if "!FAST_PATH!"=="" set "FAST_PATH=%~dp0input"
set "FAST_PATH=!FAST_PATH:"=!"

"!PYTHON_CMD!" "%~dp0pdf_to_md.py" "!FAST_PATH!" --output "%~dp0Output"
echo.
pause
goto MENU


REM ── 4. Меню примусового вибору рушія OCR ──
:FORCE_OCR_MENU
cls
echo ================================================================
echo               ПРИМУСОВИЙ ВИБІР РУШІЯ OCR
echo ================================================================
echo.
echo  [1] Google Gemini Vision ^(Рекомендовано: найшвидший та безкоштовний^)
echo  [2] Mistral AI Document OCR ^(mistral-ocr-latest / спеціалізований^)
echo  [3] OpenAI GPT-4o Vision
echo  [4] Anthropic Claude 3.5 Sonnet Vision
echo  [5] DeepSeek Vision
echo  [6] Tesseract OCR ^(Локальний офлайн^)
echo  [7] Автоматичний вибір рушія
echo  [0] Назад у головне меню
echo.
echo ================================================================
set "OCR_CHOICE="
set /p "OCR_CHOICE=Оберіть рушій OCR [0-7]: "

if "!OCR_CHOICE!"=="0" goto MENU
set "ENGINE_NAME=auto"
if "!OCR_CHOICE!"=="1" set "ENGINE_NAME=gemini"
if "!OCR_CHOICE!"=="2" set "ENGINE_NAME=mistral"
if "!OCR_CHOICE!"=="3" set "ENGINE_NAME=openai"
if "!OCR_CHOICE!"=="4" set "ENGINE_NAME=claude"
if "!OCR_CHOICE!"=="5" set "ENGINE_NAME=deepseek"
if "!OCR_CHOICE!"=="6" set "ENGINE_NAME=tesseract"
if "!OCR_CHOICE!"=="7" set "ENGINE_NAME=auto"

echo.
set "OCR_IN_PATH="
set /p "OCR_IN_PATH=Введіть шлях до PDF або папки [за замовчуванням input]: "
if "!OCR_IN_PATH!"=="" set "OCR_IN_PATH=%~dp0input"
set "OCR_IN_PATH=!OCR_IN_PATH:"=!"

echo.
echo ----------------------------------------------------------------
echo  Запуск OCR [Рушій: !ENGINE_NAME!] для "!OCR_IN_PATH!"...
echo ----------------------------------------------------------------
"!PYTHON_CMD!" "%~dp0pdf_ocr_to_md.py" "!OCR_IN_PATH!" --engine !ENGINE_NAME! --output "%~dp0Output"
echo.
pause
goto MENU


REM ── 5. Налаштування API-ключів та рушія за замовчуванням ──
:CONFIGURE_KEYS
cls
echo ================================================================
echo               СТАТУС ТА НАЛАШТУВАННЯ РУШІЇВ OCR
echo ================================================================
echo.
"!PYTHON_CMD!" "%~dp0pdf_ocr_to_md.py" --list-engines
echo ----------------------------------------------------------------
echo  Налаштування API-ключів та вибір рушія за замовчуванням:
echo.
echo  [1] Встановити GEMINI_API_KEY
echo  [2] Встановити MISTRAL_API_KEY
echo  [3] Встановити OPENAI_API_KEY
echo  [4] Встановити ANTHROPIC_API_KEY
echo  [5] Встановити DEEPSEEK_API_KEY
echo  [6] [*] Обрати рушій OCR за замовчуванням ^(Default AI Engine^)
echo  [0] Повернутися назад
echo ----------------------------------------------------------------
set "KEY_CHOICE="
set /p "KEY_CHOICE=Оберіть варіант [0-6]: "

if "!KEY_CHOICE!"=="0" goto MENU
if "!KEY_CHOICE!"=="1" goto SET_KEY_1
if "!KEY_CHOICE!"=="2" goto SET_KEY_2
if "!KEY_CHOICE!"=="3" goto SET_KEY_3
if "!KEY_CHOICE!"=="4" goto SET_KEY_4
if "!KEY_CHOICE!"=="5" goto SET_KEY_5
if "!KEY_CHOICE!"=="6" goto SELECT_DEFAULT_ENGINE
goto CONFIGURE_KEYS

:SET_KEY_1
set /p "G_KEY=Введіть ваш Gemini API Key: "
if defined G_KEY (
    set "GEMINI_API_KEY=!G_KEY!"
    "!PYTHON_CMD!" -c "from pathlib import Path; f=Path('%~dp0.env'); lines=[l for l in (f.read_text(encoding='utf-8', errors='ignore').splitlines() if f.exists() else []) if not l.startswith('GEMINI_API_KEY=')]; lines.append('GEMINI_API_KEY=!G_KEY!'); f.write_text('\n'.join(lines).strip()+'\n', encoding='utf-8')"
    echo [OK] Збережено у .env
)
pause
goto CONFIGURE_KEYS

:SET_KEY_2
set /p "M_KEY=Введіть ваш Mistral API Key: "
if defined M_KEY (
    set "MISTRAL_API_KEY=!M_KEY!"
    "!PYTHON_CMD!" -c "from pathlib import Path; f=Path('%~dp0.env'); lines=[l for l in (f.read_text(encoding='utf-8', errors='ignore').splitlines() if f.exists() else []) if not l.startswith('MISTRAL_API_KEY=')]; lines.append('MISTRAL_API_KEY=!M_KEY!'); f.write_text('\n'.join(lines).strip()+'\n', encoding='utf-8')"
    echo [OK] Збережено у .env
)
pause
goto CONFIGURE_KEYS

:SET_KEY_3
set /p "O_KEY=Введіть ваш OpenAI API Key: "
if defined O_KEY (
    set "OPENAI_API_KEY=!O_KEY!"
    "!PYTHON_CMD!" -c "from pathlib import Path; f=Path('%~dp0.env'); lines=[l for l in (f.read_text(encoding='utf-8', errors='ignore').splitlines() if f.exists() else []) if not l.startswith('OPENAI_API_KEY=')]; lines.append('OPENAI_API_KEY=!O_KEY!'); f.write_text('\n'.join(lines).strip()+'\n', encoding='utf-8')"
    echo [OK] Збережено у .env
)
pause
goto CONFIGURE_KEYS

:SET_KEY_4
set /p "A_KEY=Введіть ваш Anthropic API Key: "
if defined A_KEY (
    set "ANTHROPIC_API_KEY=!A_KEY!"
    "!PYTHON_CMD!" -c "from pathlib import Path; f=Path('%~dp0.env'); lines=[l for l in (f.read_text(encoding='utf-8', errors='ignore').splitlines() if f.exists() else []) if not l.startswith('ANTHROPIC_API_KEY=')]; lines.append('ANTHROPIC_API_KEY=!A_KEY!'); f.write_text('\n'.join(lines).strip()+'\n', encoding='utf-8')"
    echo [OK] Збережено у .env
)
pause
goto CONFIGURE_KEYS

:SET_KEY_5
set /p "D_KEY=Введіть ваш DeepSeek API Key: "
if defined D_KEY (
    set "DEEPSEEK_API_KEY=!D_KEY!"
    "!PYTHON_CMD!" -c "from pathlib import Path; f=Path('%~dp0.env'); lines=[l for l in (f.read_text(encoding='utf-8', errors='ignore').splitlines() if f.exists() else []) if not l.startswith('DEEPSEEK_API_KEY=')]; lines.append('DEEPSEEK_API_KEY=!D_KEY!'); f.write_text('\n'.join(lines).strip()+'\n', encoding='utf-8')"
    echo [OK] Збережено у .env
)
pause
goto CONFIGURE_KEYS

:SELECT_DEFAULT_ENGINE
cls
echo ================================================================
echo         ВИБІР РУШІЯ OCR ЗА ЗАМОВЧУВАННЯМ (DEFAULT ENGINE)
echo ================================================================
echo.
echo  Поточний вибір буде діяти автоматично для всіх запусків
echo  (розумний режим, Drag-and-Drop на файл, пакетна обробка).
echo.
echo  [1] Google Gemini Vision ^(Безкоштовно 15 RPM, найшвидший^)
echo  [2] Mistral AI Document OCR ^(mistral-ocr-latest / спеціалізований^)
echo  [3] OpenAI GPT-4o Vision
echo  [4] Anthropic Claude 3.5 Sonnet Vision
echo  [5] DeepSeek Vision
echo  [6] Tesseract OCR ^(Локальний офлайн^)
echo  [7] Авто-вибір за пріоритетом якості ^(Auto^)
echo  [0] Скасувати
echo ----------------------------------------------------------------
set "DEF_CHOICE="
set /p "DEF_CHOICE=Оберіть бажаний рушій [0-7]: "

if "!DEF_CHOICE!"=="0" goto CONFIGURE_KEYS
set "SELECTED_DEF="
if "!DEF_CHOICE!"=="1" set "SELECTED_DEF=gemini"
if "!DEF_CHOICE!"=="2" set "SELECTED_DEF=mistral"
if "!DEF_CHOICE!"=="3" set "SELECTED_DEF=openai"
if "!DEF_CHOICE!"=="4" set "SELECTED_DEF=claude"
if "!DEF_CHOICE!"=="5" set "SELECTED_DEF=deepseek"
if "!DEF_CHOICE!"=="6" set "SELECTED_DEF=tesseract"
if "!DEF_CHOICE!"=="7" set "SELECTED_DEF=auto"

if defined SELECTED_DEF (
    set "DEFAULT_OCR_ENGINE=!SELECTED_DEF!"
    "!PYTHON_CMD!" -c "from pathlib import Path; f=Path('%~dp0.env'); lines=[l for l in (f.read_text(encoding='utf-8', errors='ignore').splitlines() if f.exists() else []) if not l.startswith('DEFAULT_OCR_ENGINE=')]; lines.append('DEFAULT_OCR_ENGINE=!SELECTED_DEF!'); f.write_text('\n'.join(lines).strip()+'\n', encoding='utf-8')"
    echo.
    echo [УСПІХ] Рушій за замовчуванням збережено: [!SELECTED_DEF!]
)
echo.
pause
goto CONFIGURE_KEYS


REM ── 6. Власні папки ──
:CUSTOM_DIRS
echo.
echo ----------------------------------------------------------------
echo  Власні папки для конвертації
echo ----------------------------------------------------------------
set "IN_DIR="
set "OUT_DIR="
set /p "IN_DIR=Введіть шлях до вхідної папки/файлу PDF: "
if not defined IN_DIR (
    echo [Скасовано] Вхідний шлях не вказано.
    echo.
    pause
    goto MENU
)
set "IN_DIR=!IN_DIR:"=!"

set /p "OUT_DIR=Введіть шлях до папки результатів [за замовчуванням Output]: "
set "OUT_DIR=!OUT_DIR:"=!"
if "!OUT_DIR!"=="" set "OUT_DIR=%~dp0Output"

if not exist "!IN_DIR!" (
    echo.
    echo [ПОМИЛКА] Вхідний шлях не існує: "!IN_DIR!"
    echo.
    pause
    goto MENU
)

echo.
"!PYTHON_CMD!" "%~dp0pdf_to_md.py" "!IN_DIR!" --output "!OUT_DIR!" --auto-ocr
echo.
pause
goto MENU


REM ── 7. Відкрити Output ──
:OPEN_OUTPUT
if not exist "%~dp0Output" mkdir "%~dp0Output"
start "" "%~dp0Output"
goto MENU


REM ── 0. Вихід ──
:EXIT_APP
echo.
echo Дякуємо за використання!
timeout /t 1 >nul
exit /b 0


REM ── Drag and Drop блок ──
:DRAG_DROP
set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>&1 && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ================================================================
    echo [ПОМИЛКА] Python не знайдено в системі! Встановіть Python 3.
    echo ================================================================
    pause
    exit /b 1
)

if not exist "%~dp0Output" mkdir "%~dp0Output"

echo ================================================================
echo  Пряма конвертація PDF: Drag and Drop ^(Розумний режим^)
echo ================================================================
"!PYTHON_CMD!" "%~dp0pdf_to_md.py" %* --output "%~dp0Output" --auto-ocr
echo.
echo [Готово] Результати збережено в папку: Output
echo.
pause
exit /b 0
