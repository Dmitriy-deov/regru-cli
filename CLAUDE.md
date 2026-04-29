# regru-cli

CLI-обёртка над REG.API 2.0 для управления доменами и DNS-записями на аккаунте
reg.ru. Используй её, когда пользователь просит что-то настроить с доменами:
вместо ручных `curl` к API дёргай подкоманды `./regru.py`.

## Быстрый старт

Запускать из папки скрипта (там же лежит `.env`):

```bash
./regru.py whoami      # проверить, что credentials и IP whitelist настроены
./regru.py domains     # список доменов на аккаунте
```

Если `whoami` падает — проблема либо в `.env` (нет/пустые `REGRU_USERNAME` /
`REGRU_PASSWORD`), либо в IP whitelist на стороне reg.ru («Настройки API» в
кабинете). Подскажи пользователю проверить это.

## Подкоманды

| команда | что делает |
|---------|------------|
| `whoami` | статистика пользователя (тест аутентификации) |
| `domains` | список всех доменов на аккаунте |
| `info <domain>` | детали по домену |
| `check <domain>` | доступен ли домен для регистрации |
| `nss <domain> <ns1> <ns2> [...]` | сменить NS-сервера |
| `dns <domain>` | все DNS-записи зоны |
| `dns-add <domain> <sub> <type> <value>` | добавить запись |
| `dns-remove <domain> <sub> <type> [value]` | удалить запись |
| `raw <category> <method> [k=v ...]` | произвольный API-вызов |

`<sub>` — поддомен (`www`, `api`) или `@` для корня. `<type>` — `A`, `AAAA`,
`CNAME`, `MX`, `TXT`, `NS`.

## Примеры

```bash
# A-запись для api.example.com -> 1.2.3.4
./regru.py dns-add example.com api A 1.2.3.4

# CNAME blog.example.com -> ghost.io
./regru.py dns-add example.com blog CNAME ghost.io

# MX (приоритет + хост в одной строке через пробел)
./regru.py dns-add example.com @ MX "10 mail.example.com"

# TXT (например, SPF)
./regru.py dns-add example.com @ TXT "v=spf1 include:_spf.google.com ~all"

# Удалить все A-записи api.example.com
./regru.py dns-remove example.com api A

# Удалить конкретное значение (если несколько A-записей)
./regru.py dns-remove example.com api A 1.2.3.4

# Сменить NS на Cloudflare
./regru.py nss example.com lia.ns.cloudflare.com tom.ns.cloudflare.com

# Произвольный вызов API (если нужного алиаса нет)
./regru.py raw domain get_prices
```

## Несколько аккаунтов (профили)

Скрипт умеет работать с любым числом аккаунтов reg.ru. Каждому аккаунту —
свой файл `.env.<имя>` рядом со скриптом, того же формата, что и `.env`:

```
REGRU_USERNAME=...
REGRU_PASSWORD=...
```

Чтобы добавить новый профиль — создай файл `.env.<имя>` (он автоматически
попадает под `.gitignore`). Какие профили есть сейчас — смотри `ls -a` в
рабочей папке.

Запуск:

```bash
./regru.py whoami                          # дефолтный .env
./regru.py --profile work whoami           # явно выбранный профиль
REGRU_PROFILE=work ./regru.py domains      # то же через env-переменную,
                                           # удобно если команд подряд много
```

Если пользователь говорит «проверь второй аккаунт» / «добавь поддомен на
другом аккаунте» — спроси, какой профиль использовать (либо ориентируйся
по контексту: домен принадлежит конкретному аккаунту).

Каждый аккаунт reg.ru имеет **свой IP whitelist** в кабинете. Если `whoami`
под профилем падает с ошибкой доступа, скорее всего текущий внешний IP
не добавлен в whitelist того конкретного аккаунта — это не баг скрипта.

## На что обратить внимание

- **Платные операции** (`domain/create`, `domain/renew`, `domain/transfer`)
  намеренно не обёрнуты — они списывают деньги. Если пользователь просит
  купить/продлить домен, явно подтверди и используй `raw`.
- Все ответы — JSON в stdout. Используй `jq` или парсинг в Python для
  извлечения нужных полей.
- `result != "success"` -> exit 1 + JSON ошибки в stdout. Можно ловить через
  `set -e` или проверять exit code.
- Credentials никогда не логируй и не вставляй в чат — они в `.env`, который
  скрипт читает локально.
