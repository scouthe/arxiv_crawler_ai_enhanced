#!/usr/bin/env python3
"""Convert vmess:// links or subscriptions to a Clash/Mihomo YAML file.

This script intentionally uses only the Python standard library, so it can run
locally without subconverter, Docker, pip, or any external service.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any


VMESS_PREFIX = "vmess://"
SUPPORTED_NETWORKS = {"tcp", "ws", "h2", "http", "grpc"}
UNSUPPORTED_NETWORK_HINTS = {
    "kcp": "mKCP/KCP is not supported by Clash/Mihomo VMess proxies.",
    "mkcp": "mKCP/KCP is not supported by Clash/Mihomo VMess proxies.",
    "quic": "QUIC transport is not supported by Clash/Mihomo VMess proxies.",
}


class ConvertError(Exception):
    """Raised when a vmess node cannot be converted."""


def add_base64_padding(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    missing = len(value) % 4
    if missing:
        value += "=" * (4 - missing)
    return value


def decode_base64_text(value: str) -> str:
    payload = add_base64_padding(value)
    errors: list[Exception] = []

    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decoder(payload).decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - collect both decoder errors
            errors.append(exc)

    raise ConvertError(f"base64 decode failed: {errors[-1]}")


def load_source(source: str | None, timeout: int) -> str:
    if not source or source == "-":
        return sys.stdin.read()

    if source.startswith(VMESS_PREFIX):
        return source

    if os.path.exists(source):
        with open(source, "r", encoding="utf-8") as handle:
            return handle.read()

    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(
            source,
            headers={"User-Agent": "vmess-to-clash/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")

    return source


def extract_vmess_links(text: str) -> list[str]:
    text = urllib.parse.unquote(text.strip())
    links: list[str] = []

    for line in text.replace("\r", "\n").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for token in re.split(r"\s+", stripped):
            token = token.strip().strip(",;")
            if token.startswith(VMESS_PREFIX):
                links.append(token)

    if links:
        return links

    try:
        decoded_subscription = decode_base64_text(text)
    except ConvertError:
        decoded_subscription = ""

    if decoded_subscription and decoded_subscription != text:
        return extract_vmess_links(decoded_subscription)

    if text.startswith("{") and text.endswith("}"):
        encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")
        return [VMESS_PREFIX + encoded]

    return []


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "tls", "yes", "on"}


def as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConvertError(f"invalid integer value: {value!r}") from exc


def split_csv(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def normalize_path(value: Any, default: str = "/") -> str:
    if value is None or value == "":
        return default
    path = urllib.parse.unquote(str(value))
    return path or default


def parse_vmess_json(link: str) -> dict[str, Any]:
    payload = urllib.parse.unquote(link[len(VMESS_PREFIX) :]).strip()
    decoded = decode_base64_text(payload)

    try:
        data = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ConvertError(f"vmess JSON parse failed: {exc}") from exc

    if not isinstance(data, dict):
        raise ConvertError("vmess payload is not a JSON object")

    return data


def parse_vmess_uri(link: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qs(parsed.query)

    def q(name: str, default: str = "") -> str:
        values = query.get(name)
        return urllib.parse.unquote(values[0]) if values else default

    try:
        port = parsed.port
    except ValueError as exc:
        raise ConvertError(f"invalid URI port: {exc}") from exc

    if not parsed.username or not parsed.hostname or not port:
        raise ConvertError("unsupported vmess URI format")

    return {
        "ps": urllib.parse.unquote(parsed.fragment) or parsed.hostname,
        "add": parsed.hostname,
        "port": port,
        "id": urllib.parse.unquote(parsed.username),
        "aid": q("alterId", "0"),
        "scy": first_non_empty(q("security"), q("cipher"), "auto"),
        "net": first_non_empty(q("type"), q("network"), "tcp"),
        "type": q("headerType"),
        "host": q("host"),
        "path": q("path"),
        "tls": q("tls"),
        "sni": q("sni"),
        "alpn": q("alpn"),
        "fp": q("fp"),
    }


def parse_vmess_link(link: str) -> dict[str, Any]:
    try:
        return parse_vmess_json(link)
    except ConvertError as json_error:
        try:
            return parse_vmess_uri(link)
        except ConvertError as uri_error:
            raise ConvertError(f"{json_error}; {uri_error}") from uri_error


def vmess_to_proxy(data: dict[str, Any], index: int) -> dict[str, Any]:
    server = first_non_empty(data.get("add"), data.get("server"), data.get("address"))
    port = first_non_empty(data.get("port"))
    uuid = first_non_empty(data.get("id"), data.get("uuid"))

    if not server:
        raise ConvertError("missing server/add")
    if not port:
        raise ConvertError("missing port")
    if not uuid:
        raise ConvertError("missing uuid/id")

    name = first_non_empty(data.get("ps"), data.get("name"), data.get("remarks"))
    name = urllib.parse.unquote(str(name)) if name else f"vmess-{index}"

    network = str(first_non_empty(data.get("net"), data.get("network"), "tcp")).lower()
    header_type = str(first_non_empty(data.get("type"), data.get("headerType"), "")).lower()
    host = first_non_empty(data.get("host"), data.get("peer"))
    path = first_non_empty(data.get("path"), data.get("serviceName"))
    tls_enabled = as_bool(data.get("tls"))

    if network == "http2":
        network = "h2"
    if network == "tcp" and header_type == "http":
        network = "http"

    if network not in SUPPORTED_NETWORKS:
        hint = UNSUPPORTED_NETWORK_HINTS.get(
            network,
            "Clash/Mihomo VMess only supports tcp, ws, h2, http, and grpc transports.",
        )
        raise ConvertError(f"unsupported vmess transport {network!r}: {hint}")

    proxy: dict[str, Any] = {
        "name": name,
        "type": "vmess",
        "server": str(server),
        "port": as_int(port),
        "uuid": str(uuid),
        "alterId": as_int(first_non_empty(data.get("aid"), data.get("alterId")), 0),
        "cipher": str(first_non_empty(data.get("scy"), data.get("cipher"), "auto")),
        "udp": True,
    }

    if tls_enabled:
        proxy["tls"] = True
        servername = first_non_empty(data.get("sni"), data.get("servername"), host)
        if servername:
            proxy["servername"] = str(servername)
        alpn = split_csv(data.get("alpn"))
        if alpn:
            proxy["alpn"] = alpn
        fingerprint = first_non_empty(data.get("fp"), data.get("fingerprint"))
        if fingerprint:
            proxy["client-fingerprint"] = str(fingerprint)

    if network and network != "tcp":
        proxy["network"] = network

    if network == "ws":
        ws_opts: dict[str, Any] = {}
        if path:
            ws_opts["path"] = normalize_path(path)
        if host:
            ws_opts["headers"] = {"Host": str(host)}
        proxy["ws-opts"] = ws_opts
    elif network == "h2":
        h2_opts: dict[str, Any] = {}
        if path:
            h2_opts["path"] = normalize_path(path)
        hosts = split_csv(host)
        if hosts:
            h2_opts["host"] = hosts
        proxy["h2-opts"] = h2_opts
    elif network == "grpc":
        service_name = normalize_path(path, default="").lstrip("/")
        proxy["grpc-opts"] = {"grpc-service-name": service_name}
    elif network == "http":
        http_opts: dict[str, Any] = {
            "method": "GET",
            "path": split_csv(path) or ["/"],
        }
        hosts = split_csv(host)
        if hosts:
            http_opts["headers"] = {"Host": hosts}
        proxy["http-opts"] = http_opts

    return proxy


def unique_proxy_names(proxies: list[dict[str, Any]]) -> None:
    seen: dict[str, int] = {}
    for proxy in proxies:
        base = str(proxy["name"]).strip() or "vmess"
        count = seen.get(base, 0) + 1
        seen[base] = count
        proxy["name"] = base if count == 1 else f"{base} {count}"


def build_clash_config(proxies: list[dict[str, Any]], group_name: str) -> dict[str, Any]:
    proxy_names = [str(proxy["name"]) for proxy in proxies]
    groups: list[dict[str, Any]] = []

    select_group_proxies = proxy_names + ["DIRECT"]
    if len(proxy_names) > 1:
        select_group_proxies = ["AUTO"] + select_group_proxies

    groups.append(
        {
            "name": group_name,
            "type": "select",
            "proxies": select_group_proxies,
        }
    )

    if len(proxy_names) > 1:
        groups.append(
            {
                "name": "AUTO",
                "type": "url-test",
                "proxies": proxy_names,
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
            }
        )

    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxies,
        "proxy-groups": groups,
        "rules": [f"MATCH,{group_name}"],
    }


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return "null"
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def dump_yaml(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent

    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, dict):
                if item:
                    lines.append(f"{prefix}{key}:")
                    lines.extend(dump_yaml(item, indent + 2))
                else:
                    lines.append(f"{prefix}{key}: {{}}")
            elif isinstance(item, list):
                if item:
                    lines.append(f"{prefix}{key}:")
                    lines.extend(dump_yaml(item, indent + 2))
                else:
                    lines.append(f"{prefix}{key}: []")
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines

    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{prefix}- {{}}")
                    continue

                keys = list(item.keys())
                first_key = keys[0]
                first_value = item[first_key]
                if isinstance(first_value, (dict, list)):
                    lines.append(f"{prefix}- {first_key}:")
                    lines.extend(dump_yaml(first_value, indent + 4))
                else:
                    lines.append(f"{prefix}- {first_key}: {yaml_scalar(first_value)}")

                for key in keys[1:]:
                    nested_value = item[key]
                    nested_prefix = " " * (indent + 2)
                    if isinstance(nested_value, dict):
                        if nested_value:
                            lines.append(f"{nested_prefix}{key}:")
                            lines.extend(dump_yaml(nested_value, indent + 4))
                        else:
                            lines.append(f"{nested_prefix}{key}: {{}}")
                    elif isinstance(nested_value, list):
                        if nested_value:
                            lines.append(f"{nested_prefix}{key}:")
                            lines.extend(dump_yaml(nested_value, indent + 4))
                        else:
                            lines.append(f"{nested_prefix}{key}: []")
                    else:
                        lines.append(f"{nested_prefix}{key}: {yaml_scalar(nested_value)}")
            elif isinstance(item, list):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines

    return [f"{prefix}{yaml_scalar(value)}"]


def convert(source_text: str, group_name: str) -> tuple[str, int]:
    links = extract_vmess_links(source_text)
    if not links:
        raise ConvertError("no vmess:// links found")

    proxies: list[dict[str, Any]] = []
    failures: list[str] = []

    for index, link in enumerate(links, start=1):
        try:
            proxies.append(vmess_to_proxy(parse_vmess_link(link), index))
        except ConvertError as exc:
            failures.append(f"node {index}: {exc}")

    if not proxies:
        raise ConvertError("all vmess nodes failed to convert: " + "; ".join(failures))

    unique_proxy_names(proxies)
    config = build_clash_config(proxies, group_name)
    yaml_text = "\n".join(dump_yaml(config)) + "\n"
    return yaml_text, len(failures)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert vmess:// links or a vmess subscription to Clash/Mihomo YAML.",
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="vmess:// link, local file, subscription URL, or '-' for stdin",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="clash.yaml",
        help="output YAML path, default: clash.yaml",
    )
    parser.add_argument(
        "--group",
        default="PROXY",
        help="proxy group name, default: PROXY",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP subscription fetch timeout in seconds, default: 20",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        source_text = load_source(args.source, args.timeout)
        yaml_text, failure_count = convert(source_text, args.group)
    except Exception as exc:  # noqa: BLE001 - print a clear CLI error
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path = os.path.abspath(args.output)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(yaml_text)

    print(f"wrote {output_path}")
    if failure_count:
        print(f"warning: skipped {failure_count} invalid node(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
