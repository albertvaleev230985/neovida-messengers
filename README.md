# Telegram, WhatsApp и MAX в Claude

Подключаем личные мессенджеры к Claude Code (и к Codex), чтобы спрашивать агента:
«что мне писали в WhatsApp за сегодня», «найди в MAX, где договаривались про оплату»,
«перескажи рабочий чат в Telegram», «подготовь ответ клиенту».

## Как подключить

Открой Claude Code и вставь одну фразу:

```
Подключи мне Telegram, WhatsApp и MAX по инструкции https://raw.githubusercontent.com/albertvaleev230985/neovida-messengers/main/SETUP.md
```

Дальше Claude всё сделает сам. От тебя понадобится:

- **MAX**: отсканировать QR телефоном (Настройки → Устройства → Подключить устройство).
- **WhatsApp**: включить VPN на компьютере и отсканировать QR (Настройки → Связанные устройства).
- **Telegram**: прислать агенту в чат два кода, которые придут в само приложение Telegram. Ключи на my.telegram.org агент получает сам.

Займёт 10–15 минут. Работает на macOS и Windows.

## Что внутри

- `max/max_mcp.py`: коннектор MAX от NEOVIDA (на библиотеке PyMax), вход по QR.
- `whatsapp/wa_mcp.py`: запуск моста [verygoodplugins/whatsapp-mcp](https://github.com/verygoodplugins/whatsapp-mcp) v0.7.0
  и его MCP-сервера. Готовые сборки моста под Mac и Windows лежат в релизе, наш патч (вход кодом по номеру,
  QR в файл) в `whatsapp/patch/`.
- Telegram ставится из открытого плагина [bchewy/telegram-agent-plugin](https://github.com/bchewy/codex-telegram-plugin),
  а `telegram/tg_setup.py` от NEOVIDA сам получает ключи на my.telegram.org и входит в аккаунт: от ученика только коды.

## Правила

- Всё хранится только на твоём компьютере, в папке `.neovida-messengers`.
- Читать и искать переписку агент может свободно. Отправлять от твоего имени только после твоего «ок».
- WhatsApp и MAX подключаются неофициально: никаких рассылок, иначе аккаунт могут заблокировать.

NEOVIDA · neovida.ai
