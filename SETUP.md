# Инструкция для Claude: подключить Telegram, WhatsApp и MAX

Ты агент (Claude Code или Codex) на компьютере ученика курса NEOVIDA. Твоя задача: подключить личные
Telegram, WhatsApp и MAX ученика как MCP-серверы, чтобы он мог читать и искать переписку прямо из чата с тобой.
Делай всё сам, по шагам, коротко сообщая ученику, что происходит. Ученик не программист: терминал он не открывает,
файлы не раскладывает, на сайтах ничего не заполняет. От него нужно только то, что физически не сделаешь ты:
отсканировать два QR-кода (MAX и WhatsApp), прислать тебе в чат два кода, которые Telegram пришлёт в само
приложение Telegram, и ввести облачный пароль Telegram в окошке на экране, если он включён.

Схема та же, что у Альберта Валеева, только всё живёт на компьютере ученика, без сервера:

| Мессенджер | Что ставим | Вход |
|---|---|---|
| Telegram | открытый плагин `bchewy/telegram-agent-plugin` (Telethon, MIT) | код из Telegram, ученик в терминале |
| WhatsApp | мост `verygoodplugins/whatsapp-mcp` v0.7.0 + патч NEOVIDA, готовые сборки в нашем релизе | QR в браузере или код по номеру |
| MAX | коннектор NEOVIDA `max_mcp.py` на PyMax | QR в браузере |

Все файлы лежат в папке `~/.neovida-messengers` (на Windows `%USERPROFILE%\.neovida-messengers`).

Адрес репозитория: `https://github.com/albertvaleev230985/neovida-messengers`
Сырые файлы: `https://raw.githubusercontent.com/albertvaleev230985/neovida-messengers/main/<путь>`

---

## Шаг 0. Спроси и проверь

1. Спроси ученика одним сообщением: какие мессенджеры подключаем (по умолчанию все три) и есть ли у него
   WhatsApp и MAX на телефоне. Не подключай то, чего у него нет.
2. Определи систему: macOS (`uname -m` даст `arm64` или `x86_64`) или Windows (PowerShell).
3. Проверь `uv`: `uv --version`. Если нет, поставь:
   - macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   После установки найди АБСОЛЮТНЫЙ путь к uv (`which uv` или `where.exe uv`; обычно `~/.local/bin/uv`
   или `%USERPROFILE%\.local\bin\uv.exe`). Дальше в конфигах MCP используй только абсолютный путь:
   десктопное приложение Claude часто не видит PATH из терминала.
4. Создай папку `~/.neovida-messengers`.

## Шаг 1. MAX

1. Скачай `max/max_mcp.py` из репозитория в `~/.neovida-messengers/max_mcp.py`
   (macOS: `curl -fsSL -o`, Windows: `Invoke-WebRequest -OutFile`).
2. Прогрей зависимости: `uv run --script ~/.neovida-messengers/max_mcp.py status`
   (первый раз скачает библиотеки, ответ `logged_in: false` это нормально).
3. Вход: запусти сам `uv run --script ~/.neovida-messengers/max_mcp.py login` (таймаут 6 минут).
   Скрипт откроет QR в браузере и напечатает его в терминал. Скажи ученику:
   «На телефоне в MAX: Настройки → Устройства → Подключить устройство, наведи камеру на QR в браузере».
   Успех: строка `Готово: MAX подключён`. Если MAX спросит облачный пароль, скрипт будет ждать ввод:
   останови его и попроси ученика выполнить ту же команду в своём терминале и ввести пароль там.
4. Если QR истёк, просто запусти вход ещё раз. Не запускай вход больше 3 раз подряд: MAX не любит
   частые попытки.

## Шаг 2. WhatsApp

1. Важно для России: WhatsApp заблокирован, мост работает только когда на компьютере включён VPN
   (тот же, через который у ученика работает WhatsApp Web). Спроси, включён ли VPN.
2. Скачай `whatsapp/wa_mcp.py` в `~/.neovida-messengers/wa_mcp.py`.
3. Вход: запусти сам `uv run --script ~/.neovida-messengers/wa_mcp.py login` (таймаут 11 минут).
   Скрипт сам скачает мост под систему ученика, запустит его и откроет в браузере страницу с QR
   (страница обновляется сама, QR меняется каждые 20 секунд). Скажи ученику:
   «WhatsApp на телефоне: Настройки → Связанные устройства → Привязка устройства, наведи камеру на QR».
   Если камера не читает QR, запусти вход с номером: `... wa_mcp.py login --phone 79991234567`,
   тогда на странице и в выводе появится 8-значный код для пункта «Связать по номеру телефона».
4. Успех: `Готово: WhatsApp привязан`. Мост остаётся работать в фоне, история подтянется с телефона
   за несколько минут. После перезагрузки компьютера мост поднимется сам при первом обращении Claude.

## Шаг 3. Telegram (ученик только присылает два кода)

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
   - Если создать приложение не вышло (ERROR): попроси ученика на минуту выключить VPN и повтори обе команды. Не больше трёх раз подряд.
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

## Шаг 4. Прописать MCP

Подставь абсолютный путь к uv и домашнюю папку. Если есть команда `claude`, используй её:

```
claude mcp add --scope user max -- "<uv>" run --script "<home>/.neovida-messengers/max_mcp.py" serve
claude mcp add --scope user whatsapp -- "<uv>" run --script "<home>/.neovida-messengers/wa_mcp.py" serve
claude mcp add --scope user telegram -- "<uv>" run --project "<home>/.neovida-messengers/telegram-plugin/telegram/mcp_server" codex-telegram serve
```

Если команды `claude` нет, допиши эти три сервера в `mcpServers` файла `~/.claude.json` (формат
`{"command": "<uv>", "args": [...]}`), не трогая остальное содержимое файла.

Если ученик пользуется ещё и приложением Claude (обычный чат, не Code), добавь те же три сервера в
`claude_desktop_config.json`: macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`.
Если ученик работает в Codex, пропиши их в `~/.codex/config.toml` секциями `[mcp_servers.telegram]`,
`[mcp_servers.whatsapp]`, `[mcp_servers.max]`, каждому `startup_timeout_sec = 60`. На Windows пути в config.toml пиши
в одинарных кавычках. Команду `claude mcp add` и файл `~/.claude.json` в Codex не используй.

## Шаг 5. Правило отправки

Claude Code: допиши в глобальный `~/.claude/CLAUDE.md` ученика (создай, если нет). Codex: допиши разделом
в `AGENTS.md` в корне рабочей папки ученика. Текст правила:

```
## Мессенджеры (Telegram, WhatsApp, MAX)
- Читать, искать и пересказывать переписку можно свободно.
- Отправлять сообщения от моего имени только так: показал точный текст и получателя, я ответил «ок», отправил.
- Никаких рассылок и массовых отправок: неофициальные клиенты, за это банят аккаунт.
```

## Шаг 6. Проверка

1. Попроси ученика полностью перезапустить приложение (Mac: Cmd + Q; Windows: выйти через значок у часов) и открыть снова:
   MCP-серверы подхватываются только при старте.
2. В новой сессии проверь каждый: «покажи 5 последних чатов в MAX / WhatsApp / Telegram».
   Для MAX сначала `max_status`, у WhatsApp `list_chats`, у Telegram `get_me` и `list_dialogs`.
3. Отчитайся ученику коротко: что подключено, что нет и почему.

## Если что-то не работает

| Симптом | Что делать |
|---|---|
| MAX: `Вход в MAX ещё не выполнен` | повторить шаг 1.3 |
| MAX: `MAX ещё подключается` | подождать минуту, повторить запрос |
| WhatsApp: пустые чаты сразу после входа | история идёт с телефона, подождать 5 минут, телефон держать онлайн |
| WhatsApp: мост не поднялся | включить VPN, `wa_mcp.py status`, лог `~/.neovida-messengers/whatsapp/bridge.log` |
| WhatsApp: «Device logged out» | удалить папку `~/.neovida-messengers/whatsapp/store` и пройти вход заново |
| Telegram: `no current user` | повторить шаг 3, пункты 5–6 (`TG login-send` и `TG login-finish`) |
| Telegram: «Код не подошёл» | код живёт несколько минут: `TG login-send` заново и свежий код |
| Инструментов нет в Claude | перезапустить Claude; проверить абсолютный путь к uv в конфиге |

Честно предупреди ученика один раз: WhatsApp и MAX подключаются через неофициальные клиенты. Для чтения
своей переписки и редких сообщений это нормальная практика, но за рассылки аккаунт могут заблокировать.
