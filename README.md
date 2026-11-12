# Fetchly

Telegram-бот, який живе в групових чатах: бачить посилання на TikTok, Instagram,
YouTube (зокрема Shorts), X/Twitter, Reddit і Facebook, завантажує медіа
(yt-dlp, запасний варіант gallery-dl) і надсилає його відповіддю на повідомлення.

## Як це працює

```
Telegram ─▶ bot-api (локальний Bot API) ─▶ gateway ─▶ Redis Stream ─▶ worker ×N
                     ▲                                                   │
                     └──────────── sendVideo / sendMediaGroup ◀──────────┘
```

1. `gateway` отримує webhook, знаходить посилання, ставить реакцію 👀 і кладе задачу в чергу.
2. `worker` бере задачу: кеш `file_id` → замок на посилання → ланцюжок екстракторів →
   відправка відповіддю → запис `file_id` у кеш → зняття реакції.
3. Якщо не вдалося, на повідомленні лишається 🤷. Текстових помилок у чат бот не пише.

Файли до 2 ГБ передаються локальному Bot API шляхом на спільному томі, без HTTP-вивантаження.

## Запуск

Потрібні Docker і Docker Compose v2.

1. Створіть бота в [@BotFather](https://t.me/BotFather) і **вимкніть privacy mode**
   (`/setprivacy` → Disable), інакше бот не бачить звичайних повідомлень у групах.
   Якщо бот уже був у групі, видаліть його і додайте знову.
2. Отримайте `api_id` та `api_hash` на <https://my.telegram.org>.
3. Підготуйте налаштування:

   ```sh
   cp .env.example .env
   ```

   Обов'язково заповніть `BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`,
   `WEBHOOK_SECRET`, `OWNER_ID`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`.
   Решта значень у `.env.example` робочі.
4. Запустіть:

   ```sh
   make up
   ```

Під час першого старту `gateway` сам виконує `logOut` у хмарному Bot API і реєструє
webhook на локальному сервері. Після `logOut` Telegram близько 10 хвилин не пускає
бота назад у хмарний API; локальному серверу це не заважає.

Міграції застосовує одноразовий сервіс `migrate`; `gateway` і `worker` чекають його
успішного завершення. Вручну: `make migrate`.

### Команди Makefile

| Команда        | Дія                                            |
|----------------|------------------------------------------------|
| `make up`      | зібрати образи і запустити все                 |
| `make down`    | зупинити (томи лишаються)                      |
| `make logs`    | логи всіх сервісів                             |
| `make lint`    | `ruff check`, `ruff format --check`, `mypy` (потрібен [uv](https://docs.astral.sh/uv/)) |
| `make migrate` | застосувати міграції                           |

### Команди бота

- `/start`, `/help`: коротка довідка.
- `/stats`: статистика за 24 години, розмір черги, мертві задачі. Лише для `OWNER_ID`.

## Змінні `.env`

Усі порти, ліміти, таймаути і токени беруться лише з `.env`; у коді значень немає.
Повний перелік із коментарями в `.env.example`.

| Група | Змінні | Призначення |
|-------|--------|-------------|
| Telegram | `BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | токен бота і дані застосунку для локального Bot API |
| | `WEBHOOK_SECRET` | секрет, яким підписані webhook-запити |
| | `OWNER_ID` | id користувача, якому доступна `/stats` |
| | `TRUSTED_USER_IDS` | id інших акаунтів власника через кому |
| | `ALLOWED_CHATS` | id чатів через кому; `*` = всі чати; порожньо = лише чати, де є `OWNER_ID` або хтось із `TRUSTED_USER_IDS` |
| | `TELEGRAM_REQUEST_TIMEOUT_SECONDS`, `TELEGRAM_RETRY_ATTEMPTS` | таймаут запиту і кількість спроб після 429 |
| Мережа | `GATEWAY_HOST`, `BOT_API_HOST`, `POSTGRES_HOST`, `REDIS_HOST` | імена сервісів у мережі compose |
| | `GATEWAY_PORT`, `BOT_API_PORT`, `POSTGRES_PORT`, `REDIS_PORT` | внутрішні порти (нестандартні) |
| | `GATEWAY_METRICS_PORT`, `WORKER_METRICS_PORT`, `WORKER_METRICS_HOST_PORTS` | порти метрик і діапазон на хості для воркерів |
| Сховища | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_PASSWORD` | доступи до Postgres і Redis |
| Прийом | `USER_RATE_PER_MINUTE`, `CHAT_RATE_PER_MINUTE`, `MAX_LINKS_PER_MESSAGE` | ліміти на користувача, чат і повідомлення |
| Відправка | `SEND_RATE_PER_CHAT_PER_MINUTE`, `SEND_RATE_GLOBAL_PER_SECOND` | ліміти Telegram на відправку |
| Медіа | `MAX_FILE_SIZE_MB`, `MAX_DURATION_SECONDS`, `MAX_VIDEO_HEIGHT`, `MAX_ALBUM_ITEMS` | обмеження на файл |
| Воркер | `WORKER_CONCURRENCY` | паралельні задачі в одному контейнері |
| | `JOB_MAX_ATTEMPTS` | спроб до переміщення в мертвий stream |
| | `JOB_CLAIM_IDLE_SECONDS`, `JOB_HEARTBEAT_SECONDS` | коли задачу завислого воркера забирає інший |
| | `JOB_STATE_TTL_SECONDS`, `QUEUE_BLOCK_SECONDS` | службові таймаути черги |
| | `DOWNLOAD_TIMEOUT_SECONDS` | жорсткий таймаут yt-dlp / gallery-dl |
| | `URL_LOCK_TTL_SECONDS`, `URL_LOCK_WAIT_SECONDS` | замок від паралельного завантаження одного посилання |
| | `CACHE_TTL_SECONDS` | час життя `file_id` у Redis (у Postgres без терміну) |
| | `PAUSE_BASE_SECONDS`, `PAUSE_MAX_SECONDS` | пауза платформи після блокування: старт і стеля |
| | `MAINTENANCE_INTERVAL_SECONDS`, `WORKER_STOP_GRACE_SECONDS` | обслуговування і час на завершення при зупинці |
| Шляхи | `SHARED_DIR`, `COOKIES_DIR` | спільний том worker ↔ bot-api і тека cookies у контейнері |
| Проксі | `PROXY_TIKTOK`, `PROXY_INSTAGRAM`, `PROXY_YOUTUBE`, `PROXY_TWITTER`, `PROXY_REDDIT`, `PROXY_FACEBOOK` | проксі на платформу; порожньо = напряму |
| Логи | `LOG_LEVEL` | рівень логування |

## Масштабування воркерів

Воркери не мають стану: черга, замки, ліміти і кеш лежать у Redis і Postgres.

```sh
docker compose up -d --scale worker=5
```

- Кожен воркер публікує метрики на окремому порту хоста з діапазону
  `WORKER_METRICS_HOST_PORTS` (типово `19091-19110`, тобто до 20 реплік). Для більшої
  кількості розширте діапазон.
- Якщо воркер упав посеред задачі, через `JOB_CLAIM_IDLE_SECONDS` її забирає інший.
- На `SIGTERM` воркер перестає брати нові задачі і закінчує поточні
  (до `WORKER_STOP_GRACE_SECONDS`).
- Задача, що не вдалася `JOB_MAX_ATTEMPTS` разів, потрапляє в stream `fetchly:jobs:dead`.
- yt-dlp і gallery-dl оновлюються під час старту контейнера воркера: щоб оновити їх,
  достатньо `docker compose restart worker`.

## Cookies

Потрібні для вмісту, що вимагає входу (частина Instagram, вікові обмеження YouTube тощо).

1. Експортуйте cookies у форматі Netscape (`cookies.txt`).
2. Покладіть файл як `./cookies/<platform>.txt`, де `<platform>` одне з:
   `tiktok`, `instagram`, `youtube`, `twitter`, `reddit`, `facebook`.
3. Файл має бути читабельним для користувача контейнера (uid 10001):
   `chmod 644 cookies/instagram.txt`.

Тека змонтована лише на читання, перезапуск не потрібен: файл копіюється для кожної
задачі. Вміст теки не потрапляє в git. Використовуйте окремий обліковий запис, а не
особистий: платформа може його заблокувати.

## Проксі

Для кожної платформи окрема змінна `PROXY_<PLATFORM>`:

```env
PROXY_INSTAGRAM=socks5://user:pass@proxy.example:1080
PROXY_TIKTOK=http://proxy.example:3128
```

Порожнє значення означає пряме з'єднання. Після зміни: `docker compose up -d worker`.

Коли платформа блокує запити (HTTP 429, вимога входу), воркери ставлять її на паузу:
`PAUSE_BASE_SECONDS`, далі вдвічі довше за кожне повторне блокування, але не більше
`PAUSE_MAX_SECONDS`. Посилання на цю платформу під час паузи одразу отримують 🤷.

## Метрики і логи

Метрики Prometheus доступні лише з хоста:

- gateway: `http://127.0.0.1:19090/metrics`
- worker: `http://127.0.0.1:19091/metrics` (наступні репліки на наступних портах;
  точний порт показує `docker compose ps`)

Основні: `fetchly_downloads_total{platform,result,cached}`, `fetchly_download_seconds`,
`fetchly_platform_blocks_total`, `fetchly_jobs_enqueued_total`, `fetchly_rate_limited_total`,
`fetchly_queue_length`, `fetchly_dead_jobs`.

Логи у форматі JSON. Текст повідомлень та імена користувачів не зберігаються і не
логуються: у логах лише id чату, платформа і результат.

## Розробка

```sh
uv sync
make lint
```

Структура пакета: `src/fetchly/` (`gateway`, `worker`, `queue`, `extractors`, `cache`,
`ratelimit`, `db`, `links`, `telemetry`).
