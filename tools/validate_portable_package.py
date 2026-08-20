from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PORTABLE_ID_RE = re.compile(
    r"^sgp_v1_[a-z][a-z0-9_]*_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

REQUIRED_TOP_LEVEL = {
    "manifest",
    "tenants",
    "customers",
    "estimates",
    "orders",
    "order_items",
    "invoices",
    "calendar_events",
    "reminders",
    "notes",
    "attachments",
}

FORBIDDEN_SECRET_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "private_url",
    "session",
    "jwt",
    "stripe",
    "sendgrid",
}


class ValidationError(ValueError):
    pass


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key, child
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _collect_ids(package: dict[str, Any]) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {}
    seen: set[str] = set()
    for section in REQUIRED_TOP_LEVEL - {"manifest"}:
        ids[section] = set()
        for index, record in enumerate(package.get(section, [])):
            portable_id = record.get("portable_id")
            _require(isinstance(portable_id, str), f"{section}[{index}] missing portable_id")
            _require(PORTABLE_ID_RE.match(portable_id) is not None, f"{section}[{index}] has invalid portable_id")
            _require(portable_id not in seen, f"duplicate portable_id: {portable_id}")
            seen.add(portable_id)
            ids[section].add(portable_id)
    return ids


def validate_package(package: dict[str, Any]) -> list[str]:
    top_level = set(package)
    _require(top_level == REQUIRED_TOP_LEVEL, f"top-level sections mismatch: {sorted(top_level ^ REQUIRED_TOP_LEVEL)}")

    manifest = package["manifest"]
    _require(manifest.get("contract_name") == "signguy-slim-portable", "manifest contract_name mismatch")
    _require(manifest.get("contract_version") == "1.0.0", "manifest contract_version mismatch")
    _require(manifest.get("source_app") == "SIGNGUY-SLIM", "manifest source_app mismatch")
    _require(manifest.get("contains_secrets") is False, "manifest contains_secrets must be false")
    _require(PORTABLE_ID_RE.match(str(manifest.get("package_id", ""))) is not None, "manifest package_id invalid")

    for path, key, child in _walk(package):
        lowered = key.lower()
        if lowered != "contains_secrets":
            _require(
                not any(forbidden in lowered for forbidden in FORBIDDEN_SECRET_KEYS),
                f"forbidden secret-like key {key!r} at {path}",
            )
        if (key.endswith("portable_id") or key == "package_id") and child is not None:
            _require(PORTABLE_ID_RE.match(str(child)) is not None, f"invalid portable id at {path}.{key}")

    ids = _collect_ids(package)
    tenant_ids = ids["tenants"]
    _require(bool(tenant_ids), "at least one tenant is required")

    def require_tenant(section: str) -> None:
        for record in package[section]:
            _require(record.get("tenant_portable_id") in tenant_ids, f"{section} references unknown tenant")

    for section in REQUIRED_TOP_LEVEL - {"manifest", "tenants"}:
        require_tenant(section)

    customer_ids = ids["customers"]
    estimate_ids = ids["estimates"]
    order_ids = ids["orders"]
    order_item_ids = ids["order_items"]
    invoice_ids = ids["invoices"]
    event_ids = ids["calendar_events"]

    for estimate in package["estimates"]:
        _require(estimate["customer_portable_id"] in customer_ids, "estimate references unknown customer")
        converted = estimate.get("converted_order_portable_id")
        if converted:
            _require(converted in order_ids, "estimate references unknown converted order")

    for order in package["orders"]:
        _require(order["customer_portable_id"] in customer_ids, "order references unknown customer")
        source = order.get("source_estimate_portable_id")
        if source:
            _require(source in estimate_ids, "order references unknown source estimate")

    for item in package["order_items"]:
        _require(item["order_portable_id"] in order_ids, "order item references unknown order")
        source = item.get("source_estimate_portable_id")
        if source:
            _require(source in estimate_ids, "order item references unknown source estimate")

    seen_invoice_orders: set[str] = set()
    for invoice in package["invoices"]:
        _require(invoice["order_portable_id"] in order_ids, "invoice references unknown order")
        _require(invoice["customer_portable_id"] in customer_ids, "invoice references unknown customer")
        _require(invoice["order_portable_id"] not in seen_invoice_orders, "more than one invoice references an order")
        seen_invoice_orders.add(invoice["order_portable_id"])

    for event in package["calendar_events"]:
        order_id = event.get("order_portable_id")
        item_id = event.get("order_item_portable_id")
        if order_id:
            _require(order_id in order_ids, "calendar event references unknown order")
        if item_id:
            _require(item_id in order_item_ids, "calendar event references unknown order item")
        _require(event.get("completion_affects_production") is False, "calendar completion must not affect production")

    source_ids = customer_ids | estimate_ids | order_ids | order_item_ids | invoice_ids | event_ids
    for reminder in package["reminders"]:
        _require(reminder["source_portable_id"] in source_ids, "reminder references unknown source")
    for note in package["notes"]:
        _require(note["source_portable_id"] in source_ids, "note references unknown source")
        _require(note.get("internal") is True, "Version 1 notes must be internal")
    for attachment in package["attachments"]:
        _require(attachment["source_portable_id"] in source_ids, "attachment references unknown source")
        storage_path = attachment.get("storage_path", "")
        _require(".." not in storage_path and not storage_path.startswith(("/", "\\")), "attachment storage_path must be package-relative")

    return ["package valid"]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_portable_package.py <package.json>", file=sys.stderr)
        return 2
    package = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    try:
        for message in validate_package(package):
            print(message)
    except ValidationError as exc:
        print(f"package invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
