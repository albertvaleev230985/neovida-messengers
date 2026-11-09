# Инструкция для Codex: подключить Telegram и WhatsApp

Ты Codex на компьютере ученика курса NEOVIDA. Твоя задача: подключить личные Telegram и WhatsApp ученика
как MCP-серверы, чтобы он мог читать и искать переписку прямо из чата с тобой. Делай всё сам,
по шагам, коротко сообщая ученику, что происходит. Ученик не программист: терминал он не открывает,
файлы не раскладывает, на сайтах ничего не заполняет. От него нужно только то, что физически не сделаешь ты:
отсканировать QR-код WhatsApp, прислать тебе в чат два кода, которые Telegram пришлёт в само
приложение Telegram, и ввести облачный пароль Telegram в окошке на экране, если он включён.

| Мессенджер | Что ставим | Вход | VPN |
|---|---|---|---|
| WhatsApp | мост `verygoodplugins/whatsapp-mcp` v0.7.0 + патч NEOVIDA, готовые сборки в нашем релизе | QR в браузере или код по номеру | нужен |
| Telegram | открытый плагин `bchewy/telegram-agent-plugin` (Telethon, MIT) | два кода из приложения Telegram | нужен |

Порядок: WhatsApp, потом Telegram. Оба подключаются только с VPN: в учебном зале NEOVIDA его даёт Wi-Fi,
дома у ученика свой. Никогда не проси выключить VPN: из России ты без него не работаешь и замолчишь.

Все файлы лежат в папке `~/.neovida-messengers` (на Windows `%USERPROFILE%\.neovida-messengers`).

Адрес репозитория: `https://github.com/albertvaleev230985/neovida-messengers`
Сырые файлы: `https://raw.githubusercontent.com/albertvaleev230985/neovida-messengers/main/<путь>`

Команды качают файлы и пишут в домашнюю папку: запускай их с запросом разрешения, вне песочницы.
Ученик ответит «да».

---

## Шаг 0. Спроси и проверь

1. Спроси ученика одним сообщением: какие мессенджеры подключаем (по умолчанию оба) и есть ли у него
   WhatsApp на телефоне. Не подключай то, чего у него нет.
2. Определи систему: macOS (`uname -m` даст `arm64` или `x86_64`) или Windows (PowerShell).
3. Проверь `uv`: `uv --version`. Если нет, поставь:
   - macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   После установки найди АБСОЛЮТНЫЙ путь к uv (`which uv` или `where.exe uv`; обычно `~/.local/bin/uv`
   или `%USERPROFILE%\.local\bin\uv.exe`). Дальше в конфиге Codex используй только абсолютный путь:
   приложение Codex не всегда видит PATH из терминала.
4. Создай папку `~/.neovida-messengers`.

## Шаг 1. WhatsApp

1. Скачай `whatsapp/wa_mcp.py` в `~/.neovida-messengers/wa_mcp.py`
   (macOS: `curl -fsSL -o`, Windows: `Invoke-WebRequest -OutFile`).
2. Вход: запусти сам `uv run --script ~/.neovida-messengers/wa_mcp.py login` (таймаут 11 минут).
   Скрипт сам скачает мост под систему ученика, запустит его и откроет в браузере страницу с QR
   (страница обновляется сама, QR меняется каждые 20 секунд). Скажи ученику:
   «WhatsApp на телефоне: Настройки → Связанные устройства → Привязка устройства, наведи камеру на QR».
   Если камера не читает QR, запусти вход с номером: `... wa_mcp.py login --phone 79991234567`,
   тогда на странице и в выводе появится 8-значный код для пункта «Связать по номеру телефона».
3. Успех: `Готово: WhatsApp привязан`. Мост остаётся работать в фоне, история подтянется с телефона
   за несколько минут. После перезагрузки компьютера мост поднимется сам при первом обращении Codex.

## Шаг 2. Telegram (ученик только присылает два кода)

1. Скачай архив плагина и распакуй в `~/.neovida-messengers/telegram-plugin`:
   `https://github.com/bchewy/codex-telegram-plugin/archive/ad8d98370a13a35c213e6f221ef7a74a1ea123d8.zip`
   (внутри одна папка `telegram-agent-plugin-ad8d983...`, её содержимое и есть плагин).
2. Прогрей: `uv sync --project ~/.neovida-messengers/telegram-plugin/telegram/mcp_server`.
3. Скачай помощник `telegram/tg_setup.py` в `~/.neovida-messengers/tg_setup.py`.
   Дальше `TG` это команда (абсолютные пути):
   `"<uv>" run --project "<home>/.neovida-messengers/telegram-plugin/telegram/mcp_server" python "<home>/.neovida-messengers/tg_setup.py"`
4. Спроси у ученика номер телефона, на котором его Telegram.
5. Ключи приложения (api_id и api_hash) получаешь ты, ученик на сайт не заходит:
   - `TG keys-send --phone <номер>`. Скажи ученику: «В Telegram пришло сообщение от Telegram с кодом. Пришли мне этот код сюда в чат».
   - `TG keys-finish --code <код>`. Помощник сам входит на my.telegram.org, создаёт приложение и сохраняет ключи.
   - Если создать приложение не вышло (ERROR): подожди минуту и повтори обе команды, не больше трёх раз подряд.
     Не вышло и так: скажи ученику, что Telegram доделаем с ведущим на уроке, и переходи к шагу 3.
6. Вход в аккаунт:
   - `TG login-send`. Скажи: «Пришёл второй код, уже для входа. Пришли его сюда».
   - `TG login-finish --code <код>`. Если у ученика включён облачный пароль, на его экране откроется окошко
     «Облачный пароль Telegram»: попроси ввести пароль там. В чат пароль не писать и тебе не диктовать.
7. Проверь: `"<uv>" run --project "<home>/.neovida-messengers/telegram-plugin/telegram/mcp_server" codex-telegram whoami`
   показывает аккаунт ученика. Сессия хранится в системной связке ключей (Keychain на Mac, Диспетчер учётных данных на Windows).

Правила с кодами: коды никуда не пересылай и в ответах не печатай. Предупреди ученика один раз: код из Telegram
нельзя пересылать другим людям в самом Telegram, иначе Telegram заблокирует вход. Прислать его тебе в чат можно.
Если окошко пароля не открылось, запусти `TG login-finish --code <тот же код>` ещё раз; второй вариант: ученик
один раз запускает в терминале `codex-telegram login` с теми же api_id и api_hash (они в `~/.neovida-messengers/telegram/api.json`).

## Шаг 3. Прописать коннекторы в Codex

Допиши два сервера в `~/.codex/config.toml` (Windows `%USERPROFILE%\.codex\config.toml`), не трогая остальное
содержимое файла. Подставь абсолютный путь к uv и домашнюю папку. На Windows пути пиши в одинарных кавычках.

```toml
[mcp_servers.whatsapp]
command = "<uv>"
args = ["run", "--script", "<home>/.neovida-messengers/wa_mcp.py", "serve"]
startup_timeout_sec = 60

[mcp_servers.telegram]
command = "<uv>"
args = ["run", "--project", "<home>/.neovida-messengers/telegram-plugin/telegram/mcp_server", "codex-telegram", "serve"]
startup_timeout_sec = 60
```

Если секция с таким именем уже есть, не дублируй её, а обнови.

## Шаг 4. Правило в AGENTS.md

Допиши раздел в `AGENTS.md` в корне рабочей папки ученика (его читают и Codex, и OpenCode) и в глобальный
`~/.codex/AGENTS.md` (создай, если нет). Текст правила:

```
## Мессенджеры (Telegram и WhatsApp)
- Читать, искать и пересказывать переписку можно свободно.
- Отправлять сообщения от моего имени только так: показал точный текст и получателя, я ответил «ок», отправил.
- Без рассылок и массовых отправок.
```

## Шаг 5. Проверка

1. Попроси ученика полностью закрыть Codex (Mac: Cmd + Q; Windows: выйти через значок у часов) и открыть снова:
   коннекторы подхватываются только при старте.
2. В новом чате проверь каждый: «покажи 5 последних чатов в WhatsApp / Telegram».
   У WhatsApp `list_chats`, у Telegram `get_me` и `list_dialogs`.
3. Отчитайся ученику коротко: что подключено, что нет и почему.

## Если что-то не работает

| Симптом | Что делать |
|---|---|
| WhatsApp: пустые чаты сразу после входа | история идёт с телефона, подождать 5 минут, телефон держать онлайн |
| WhatsApp: мост не поднялся | проверить VPN, `wa_mcp.py status`, лог `~/.neovida-messengers/whatsapp/bridge.log` |
| WhatsApp: «Device logged out» | удалить папку `~/.neovida-messengers/whatsapp/store` и пройти вход заново |
| WhatsApp: Windows на процессоре ARM (Snapdragon) | сборки моста под ARM нет, ставится x64: Windows 11 запускает её через эмуляцию. Не запустилась: скажи ученику, что WhatsApp на этом ноутбуке пока не встанет, и переходи к Telegram |
| Telegram: `no current user` | повторить шаг 2, пункты 5–6 (`TG login-send` и `TG login-finish`) |
| Telegram: «Код не подошёл» | код живёт несколько минут: `TG login-send` заново и свежий код |
| Коннекторов нет в Codex | полностью закрыть и открыть Codex; проверить абсолютный путь к uv в `config.toml` |
