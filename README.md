# regru-cli

CLI-обёртка над [REG.API 2.0](https://www.reg.ru/reseller/api2doc) для
управления доменами и DNS-записями на аккаунте reg.ru. Без зависимостей —
только stdlib Python 3.8+.

Главная цель папки — чтобы Claude Code (или любой скрипт) мог сам править
домены и поддомены, не зная деталей API: достаточно подкоманд.

## Какую задачу решает

reg.ru — крупнейший российский регистратор доменов, но у него только сырой
REG.API 2.0: HTTPS + form-encoded запросы + альтернативный пароль + IP
whitelist. Удобной обвязки практически нет:

- **Готового CLI у reg.ru нет** — все примеры в их документации это `curl` с
  ручной сборкой JSON в `input_data`.
- **Terraform-провайдера нет.** Если зона на reg.ru, обычные DevOps-сценарии
  («задеплоил сервис → автоматом подняли DNS») приходится писать с нуля.
- **Python-библиотек либо нет, либо заброшены** (последние коммиты
  пятилетней давности, без поддержки актуальных методов API).
- **AI-ассистенты слепы к reg.ru.** Claude Code, Cursor и аналоги отлично
  работают с Cloudflare / Route 53 через MCP-серверы, но для reg.ru приходится
  диктовать им сырые `curl`-команды и надеяться, что они не ошибутся в JSON.

`regru-cli` закрывает эту дыру:

- **Тонкая обёртка без зависимостей.** Один Python-файл, только stdlib —
  кладёшь рядом с проектом, добавляешь `.env`, и всё работает. Не нужно
  заводить виртуальное окружение или ставить пакеты.
- **Подкоманды вместо `curl`.** Вместо ручной сборки запроса к
  `zone/add_alias` пишешь `./regru.py dns-add example.com api A 1.2.3.4`.
  Типовые операции — добавление/удаление DNS-записей (A, AAAA, CNAME, MX,
  TXT, NS), смена NS-серверов, просмотр зон и информации о домене —
  закрыты алиасами. Для остальных есть `raw`.
- **Несколько аккаунтов из коробки.** Профили через `.env.<имя>` и флаг
  `--profile` — переключение между рабочим и личным аккаунтом за один флаг
  (см. раздел ниже).
- **Claude Code skill в комплекте.** Положил `skills/regru-domains` в
  `~/.claude/skills` — и можно говорить ассистенту по-русски: «добавь
  поддомен api для example.com на 1.2.3.4», «смени NS на Cloudflare»,
  «покажи DNS-зону». Claude сам подбирает команду и не лезет в `curl`.
- **Деньги под защитой.** Платные методы (`domain/create`, `domain/renew`,
  `domain/transfer`) намеренно не обёрнуты в подкоманды — чтобы AI или
  скрипт случайно не списал баланс. Вызвать их можно только через явный
  `raw`.

Кому полезно: разработчикам, у которых домены висят на reg.ru и которым
надоело лазить в личный кабинет за каждой DNS-записью; пользователям AI-IDE
(Claude Code, Cursor), которым хочется управлять зонами голосом ассистента;
скриптам деплоя, которым нужен надёжный способ поднять DNS перед выкаткой.

## Установка

```bash
git clone https://github.com/Dmitriy-deov/regru-cli.git
cd regru-cli
chmod +x regru.py
```

Дальше переходите к разделу «Настройка» — заполнить `.env` и настроить API
в кабинете reg.ru.

### Что должно быть на компьютере

| Компонент | Зачем |
|-----------|-------|
| **Python 3.8+** | сам интерпретатор для `regru.py` |
| **stdlib-модули** (`urllib`, `json`, `argparse`) | сетевые запросы и парсинг — входят в Python, ставить отдельно не надо |

Проверить, что всё на месте:

```bash
python3 --version                                                # 3.8 или выше
python3 -c "import urllib.request, json, argparse; print('OK')"  # должно напечатать OK
```

Если Python не установлен (на macOS — редкость, обычно есть из коробки или
через Xcode Command Line Tools):

```bash
# macOS — через Homebrew
brew install python

# или через официальный установщик: https://www.python.org/downloads/
```

`pip install` **не нужен** — скрипт работает на чистой стандартной библиотеке.

### Опционально (для удобства)

- `jq` — парсер JSON в командной строке: `brew install jq`. Полезно для
  вытаскивания полей из ответа: `./regru.py domains | jq '.services[].dname'`.
- `curl` — уже есть на macOS, нужен один раз для `curl ifconfig.me`, чтобы
  узнать внешний IP при настройке whitelist.

## Настройка (один раз)

### 1. Настроить API в кабинете reg.ru

Зайти на страницу: **<https://www.reg.ru/user/account/settings/api/>**
(или: личный кабинет → Настройки → API).

Там три раздела — заполнить нужно как минимум первые два:

#### 1.1. Альтернативный пароль (обязательно)

Это **отдельный пароль для API**, не равный паролю от личного кабинета.
Нажать «Настроить» → задать новый пароль → сохранить. Этот пароль потом
пойдёт в `.env` как `REGRU_PASSWORD`.

> Зачем отдельный: если случайно засветите API-пароль в логе или скрипте,
> компрометируется только API-доступ, а не весь личный кабинет.

#### 1.2. Диапазоны IP-адресов (обязательно)

Узнать ваш внешний IP:

```bash
curl ifconfig.me
```

В разделе «Диапазоны IP-адресов» нажать **«+ Добавить IP»** → вставить
полученный IP → сохранить.

Без этого шага API возвращает ошибку доступа, даже если логин/пароль
правильные. Если меняете сеть (другой Wi-Fi, VPN, мобильный интернет) — нужно
обновить IP в кабинете.

#### 1.3. Аутентификация по SSL (опционально, можно пропустить)

Этот скрипт работает по схеме «логин + альтернативный пароль» и **SSL-сертификат
не использует**. Раздел «Аутентификация по SSL» можно оставить пустым.

Если когда-нибудь захотите перейти на более безопасную аутентификацию по
RSA-сигнатуре (без передачи пароля в каждом запросе), reg.ru предлагает
сгенерировать самоподписанный сертификат:

```bash
openssl req -new -x509 -nodes -sha512 -days 365 -newkey rsa:2048 \
  -keyout my.key -out my.crt
```

`my.crt` загружается в кабинет, `my.key` хранится локально. Текущая версия
`regru.py` это не поддерживает — для перехода нужно будет дописать модуль
подписи запросов.

### 2. Заполнить `.env`

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:

```
REGRU_USERNAME=ваш_логин_reg_ru
REGRU_PASSWORD=альтернативный_пароль_из_п_1_1
```

`REGRU_USERNAME` — логин от личного кабинета reg.ru.
`REGRU_PASSWORD` — **альтернативный** пароль, который задали в шаге 1.1
(не пароль от личного кабинета).

### 3. Проверка

```bash
./regru.py whoami
```

Должен вернуть JSON со статистикой аккаунта. Если падает:

- `result: error` + `NO_AUTH` / `PASSWORD_AUTH_FAILED` → проверьте логин и
  альтернативный пароль в `.env`.
- `result: error` + `IP_EXCEEDED_ALLOWED_CONNECTION_LIMIT` или похожее про
  IP → ваш текущий внешний IP не в whitelist (шаг 1.2). Перепроверьте
  `curl ifconfig.me` и добавьте этот IP в кабинете.

## Несколько аккаунтов (профили)

Скрипт поддерживает любое число аккаунтов reg.ru через профили. Каждый
профиль — это отдельный файл рядом со скриптом, формат тот же, что и у `.env`:

```
.env              # дефолтный профиль (используется без флага)
.env.temp         # профиль "temp"
.env.work         # профиль "work"
.env.personal     # ...и т.д.
```

### Создание нового профиля

```bash
cp .env.example .env.work     # или любое другое имя
$EDITOR .env.work             # вписать REGRU_USERNAME / REGRU_PASSWORD
```

### Запуск под профилем

Через флаг `--profile`:

```bash
./regru.py --profile work whoami
./regru.py --profile temp domains
./regru.py whoami                       # без флага — дефолтный .env
```

Через переменную окружения (удобно, если команд подряд несколько):

```bash
export REGRU_PROFILE=work
./regru.py whoami
./regru.py domains
unset REGRU_PROFILE                     # вернуться к дефолтному .env
```

### IP whitelist у каждого аккаунта свой

> ⚠️ В кабинете reg.ru **whitelist привязан к аккаунту**, а не к
> ключам/паролям. Переключение профиля в скрипте не помогает, если текущий
> внешний IP не добавлен в whitelist того аккаунта (см. шаг 1.2). Признак
> проблемы: `whoami` под новым профилем падает с ошибкой про IP — добавь
> `curl ifconfig.me` в whitelist конкретного аккаунта.

## Команды

| Команда | Что делает |
|---------|------------|
| `whoami` | статистика пользователя (тест аутентификации) |
| `domains` | список всех доменов на аккаунте |
| `info <domain>` | детали по конкретному домену |
| `check <domain>` | доступен ли домен для регистрации |
| `nss <domain> <ns1> <ns2> [...]` | сменить NS-сервера |
| `dns <domain>` | все DNS-записи зоны |
| `dns-add <domain> <sub> <type> <value>` | добавить запись |
| `dns-remove <domain> <sub> <type> [value]` | удалить запись |
| `raw <category> <method> [k=v ...]` | произвольный API-вызов |

`<sub>` — поддомен (`www`, `api`, `mail`) или `@` для корня домена.
`<type>` — `A`, `AAAA`, `CNAME`, `MX`, `TXT`, `NS`.

## Примеры

```bash
# Список доменов
./regru.py domains

# A-запись: api.example.com -> 1.2.3.4
./regru.py dns-add example.com api A 1.2.3.4

# Корневая A-запись (example.com -> 1.2.3.4)
./regru.py dns-add example.com @ A 1.2.3.4

# CNAME: blog.example.com -> ghost.io
./regru.py dns-add example.com blog CNAME ghost.io

# MX (приоритет и хост через пробел)
./regru.py dns-add example.com @ MX "10 mail.example.com"

# TXT (SPF)
./regru.py dns-add example.com @ TXT "v=spf1 include:_spf.google.com ~all"

# Удалить все A-записи api.example.com
./regru.py dns-remove example.com api A

# Удалить конкретное значение (если несколько A-записей с одинаковым именем)
./regru.py dns-remove example.com api A 1.2.3.4

# Сменить NS на Cloudflare
./regru.py nss example.com lia.ns.cloudflare.com tom.ns.cloudflare.com

# Произвольный вызов API — для методов, которым нет алиаса
./regru.py raw domain get_prices
./regru.py raw service get_list servtype=domain
```

## Формат вывода

Все команды печатают JSON в stdout (`ensure_ascii=False`, кириллица читаемая).
Для извлечения полей удобно через `jq`:

```bash
./regru.py domains | jq '.services[].dname'
./regru.py dns example.com | jq '.[0].rrs[]'
```

При ошибке API скрипт завершается с exit code 1 и печатает JSON ответа в
stdout — можно ловить через `set -e` или проверкой `$?`.

## Что не обёрнуто (намеренно)

Платные операции, которые списывают деньги с баланса:

- регистрация (`domain/create`)
- продление (`domain/renew`, `service/renew`)
- перенос (`domain/transfer`)

Их можно вызвать через `raw`, но это требует осознанного действия. Пример
(только если действительно нужно):

```bash
./regru.py raw domain renew domains='[{"dname":"example.com"}]' period=1
```

## Скилл для Claude Code

В репозитории лежит готовый Claude Code skill — `skills/regru-domains/`.
Если он установлен, Claude Code автоматически активируется на фразы вроде
«добавь поддомен», «настрой DNS», «смени NS» и сам вызывает нужные команды
`regru.py` без необходимости заходить в эту папку.

### Установка скилла

Вариант 1 — **симлинк** (рекомендуется): обновления из репозитория сразу
подхватываются.

```bash
mkdir -p ~/.claude/skills
ln -s ~/Desktop/regru-cli/skills/regru-domains ~/.claude/skills/regru-domains
```

Вариант 2 — **копирование**: правки скилла из репо не подхватятся, но папка
независимая.

```bash
mkdir -p ~/.claude/skills
cp -r ~/Desktop/regru-cli/skills/regru-domains ~/.claude/skills/regru-domains
```

После установки в активной сессии Claude Code: команда `/reload-plugins`
(или перезапуск Claude Code) — скилл подтянется в список.

Проверка: попросите Claude Code «покажи DNS-зону example.com» — он должен
сам вызвать `./regru.py dns example.com`, не задавая уточняющих вопросов.

### Удаление

```bash
rm ~/.claude/skills/regru-domains            # симлинк
# или
rm -rf ~/.claude/skills/regru-domains        # скопированную папку
```

## Файлы в папке

- `regru.py` — сам CLI (исполняемый).
- `.env.example` — шаблон credentials.
- `.env` — реальные credentials (создать самостоятельно, в `.gitignore`).
- `CLAUDE.md` — инструкция для Claude Code, когда он работает внутри этой папки.
- `skills/regru-domains/SKILL.md` — Claude Code skill (см. раздел выше).
- `README.md` — этот файл.
- `LICENSE` — лицензия MIT.
- `.gitignore` — исключения для git.

## Лицензия

[MIT](LICENSE) — © 2026 Dmitrij Tamarov, [za-ai.ru](https://za-ai.ru).
