#!/usr/bin/env python3
"""regru.py — CLI-обёртка над REG.API 2.0 для управления доменами и DNS на reg.ru.

Зависимости: только stdlib Python 3.8+.
Документация API: https://www.reg.ru/reseller/api2doc
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.reg.ru/api/regru2"


def load_credentials() -> tuple[str, str]:
    """Читает REGRU_USERNAME/REGRU_PASSWORD из env, иначе из .env (или .env.<profile>) рядом со скриптом.

    Профиль определяется через --profile (ставит REGRU_PROFILE в env) либо
    переменную окружения REGRU_PROFILE. Без профиля читается .env.
    """
    here = Path(__file__).resolve().parent
    profile = os.environ.get("REGRU_PROFILE", "").strip()
    env_file = here / (f".env.{profile}" if profile else ".env")
    if profile and not env_file.exists():
        sys.exit(f"ошибка: профиль '{profile}' не найден ({env_file} нет)")
    # Для дефолтного .env допускаем отсутствие — credentials могут быть в окружении.
    profile_env: dict[str, str] = {}
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            profile_env[key.strip()] = value.strip().strip('"').strip("'")
    # При активном профиле его значения перебивают окружение, иначе наоборот.
    if profile:
        user = profile_env.get("REGRU_USERNAME", "").strip()
        pwd = profile_env.get("REGRU_PASSWORD", "").strip()
    else:
        for k, v in profile_env.items():
            os.environ.setdefault(k, v)
        user = os.environ.get("REGRU_USERNAME", "").strip()
        pwd = os.environ.get("REGRU_PASSWORD", "").strip()
    if not user or not pwd:
        hint = f".env.{profile}" if profile else ".env"
        sys.exit(
            f"ошибка: не заданы REGRU_USERNAME / REGRU_PASSWORD в {hint}.\n"
            "скопируй .env.example -> .env (или .env.<profile>) и заполни"
        )
    return user, pwd


def call(category: str, method: str, payload: dict | None = None) -> dict:
    """POST на api.reg.ru/api/regru2/<category>/<method> с input_format=json."""
    user, pwd = load_credentials()
    form = {
        "username": user,
        "password": pwd,
        "output_format": "json",
        "input_format": "json",
        "input_data": json.dumps(payload or {}, ensure_ascii=False),
    }
    data = urllib.parse.urlencode(form).encode("utf-8")
    url = f"{API_BASE}/{category}/{method}"
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"HTTP {e.code} от reg.ru: {err_body}")
    except urllib.error.URLError as e:
        sys.exit(f"сетевая ошибка: {e}")

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        sys.exit(f"не JSON в ответе: {body}")

    if result.get("result") != "success":
        sys.exit(json.dumps(result, ensure_ascii=False, indent=2))
    return result.get("answer", {})


def emit(answer: dict) -> None:
    print(json.dumps(answer, ensure_ascii=False, indent=2))


# --- подкоманды -------------------------------------------------------------


def cmd_whoami(_args) -> None:
    emit(call("user", "get_statistics"))


def cmd_domains(_args) -> None:
    emit(call("service", "get_list", {"servtype": "domain"}))


def cmd_info(args) -> None:
    emit(call("service", "get_info", {"domain_name": args.domain}))


def cmd_check(args) -> None:
    emit(call("domain", "check", {"domain_name": args.domain}))


def cmd_nss(args) -> None:
    if len(args.ns) < 2:
        sys.exit("nss: нужно минимум 2 NS-сервера")
    nss = {f"ns{i}": ns for i, ns in enumerate(args.ns)}
    emit(call("domain", "update_nss", {
        "domains": [{"dname": args.domain}],
        "nss": nss,
    }))


def cmd_dns(args) -> None:
    emit(call("zone", "get_resource_records", {"domains": [{"dname": args.domain}]}))


def cmd_dns_add(args) -> None:
    base: dict = {"domains": [{"dname": args.domain}], "subdomain": args.subdomain}
    rtype = args.type.upper()
    if rtype == "A":
        method, base["ipaddr"] = "add_alias", args.value
    elif rtype == "AAAA":
        method, base["ipaddr"] = "add_aaaa", args.value
    elif rtype == "CNAME":
        method, base["canonical_name"] = "add_cname", args.value
    elif rtype == "MX":
        parts = args.value.split(maxsplit=1)
        if len(parts) != 2:
            sys.exit("MX: value должен быть 'priority host' (напр. '10 mail.example.com')")
        method = "add_mx"
        base["priority"], base["mail_server"] = parts
    elif rtype == "TXT":
        method, base["text"] = "add_txt", args.value
    elif rtype == "NS":
        method, base["dns_server"] = "add_ns", args.value
    else:
        sys.exit(f"неподдерживаемый тип записи: {args.type} (A/AAAA/CNAME/MX/TXT/NS)")
    emit(call("zone", method, base))


def cmd_dns_remove(args) -> None:
    payload: dict = {
        "domains": [{"dname": args.domain}],
        "subdomain": args.subdomain,
        "record_type": args.type.upper(),
    }
    if args.value:
        payload["content"] = args.value
    emit(call("zone", "remove_record", payload))


def cmd_raw(args) -> None:
    payload: dict = {}
    for kv in args.params:
        if "=" not in kv:
            sys.exit(f"raw: параметр '{kv}' должен быть в формате key=value")
        k, _, v = kv.partition("=")
        try:
            payload[k] = json.loads(v)
        except json.JSONDecodeError:
            payload[k] = v
    emit(call(args.category, args.method, payload))


# --- argparse ---------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regru",
        description="CLI для управления доменами и DNS на reg.ru через REG.API 2.0",
    )
    p.add_argument(
        "--profile",
        metavar="NAME",
        help="имя профиля; читает .env.<NAME> вместо .env (можно через REGRU_PROFILE)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="проверить аутентификацию (user/get_statistics)") \
        .set_defaults(func=cmd_whoami)
    sub.add_parser("domains", help="список доменов на аккаунте") \
        .set_defaults(func=cmd_domains)

    pi = sub.add_parser("info", help="детали по домену")
    pi.add_argument("domain")
    pi.set_defaults(func=cmd_info)

    pc = sub.add_parser("check", help="проверить доступность домена для регистрации")
    pc.add_argument("domain")
    pc.set_defaults(func=cmd_check)

    pn = sub.add_parser("nss", help="сменить NS-сервера домена")
    pn.add_argument("domain")
    pn.add_argument("ns", nargs="+", help="NS-сервера (минимум 2)")
    pn.set_defaults(func=cmd_nss)

    pd = sub.add_parser("dns", help="список DNS-записей домена")
    pd.add_argument("domain")
    pd.set_defaults(func=cmd_dns)

    pda = sub.add_parser("dns-add", help="добавить DNS-запись")
    pda.add_argument("domain")
    pda.add_argument("subdomain", help="поддомен ('@' для корня)")
    pda.add_argument("type", help="A | AAAA | CNAME | MX | TXT | NS")
    pda.add_argument("value", help="значение (для MX: 'priority host')")
    pda.set_defaults(func=cmd_dns_add)

    pdr = sub.add_parser("dns-remove", help="удалить DNS-запись")
    pdr.add_argument("domain")
    pdr.add_argument("subdomain")
    pdr.add_argument("type", help="A | AAAA | CNAME | MX | TXT | NS")
    pdr.add_argument("value", nargs="?", help="конкретное значение (опционально)")
    pdr.set_defaults(func=cmd_dns_remove)

    pr = sub.add_parser("raw", help="произвольный API-вызов (escape hatch)")
    pr.add_argument("category", help="например: domain, zone, service, user")
    pr.add_argument("method", help="например: get_details")
    pr.add_argument("params", nargs="*", help="key=value (value парсится как JSON если можно)")
    pr.set_defaults(func=cmd_raw)

    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.profile:
        os.environ["REGRU_PROFILE"] = args.profile
    args.func(args)


if __name__ == "__main__":
    main()
