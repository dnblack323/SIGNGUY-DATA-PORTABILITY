from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "signguy-slim-portable-v1.schema.json"

PORTABLE_ID_RE = re.compile(
    r"^sgp_v1_[a-z][a-z0-9_]*_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

SECTIONS = [
    "tenants",
    "users",
    "customers",
    "estimates",
    "estimate_items",
    "orders",
    "order_items",
    "work_orders",
    "invoices",
    "calendar_events",
    "reminders",
    "notes",
    "attachments",
    "audit_events",
]

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

SOURCE_TYPE_TO_SECTION = {
    "customer": "customers",
    "estimate": "estimates",
    "estimate_item": "estimate_items",
    "order": "orders",
    "order_item": "order_items",
    "work_order": "work_orders",
    "invoice": "invoices",
    "calendar_event": "calendar_events",
    "reminder": "reminders",
    "note": "notes",
    "attachment": "attachments",
}


class ValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key, child
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_json_schema(package: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_schema(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(package), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "$" + "".join(f"[{part!r}]" if isinstance(part, int) else f".{part}" for part in first.path)
        raise ValidationError(f"schema validation failed at {location}: {first.message}")
    return ["json schema valid"]


def _collect_records(package: dict[str, Any]) -> tuple[dict[str, dict[str, dict]], dict[str, str], dict[str, str]]:
    by_section: dict[str, dict[str, dict]] = {section: {} for section in SECTIONS}
    id_to_section: dict[str, str] = {}
    id_to_tenant: dict[str, str] = {}
    for section in SECTIONS:
        for index, record in enumerate(package[section]):
            portable_id = record.get("portable_id")
            _require(PORTABLE_ID_RE.match(str(portable_id or "")) is not None, f"{section}[{index}] invalid portable_id")
            _require(portable_id not in id_to_section, f"duplicate portable_id: {portable_id}")
            by_section[section][portable_id] = record
            id_to_section[portable_id] = section
            if section == "tenants":
                id_to_tenant[portable_id] = portable_id
            else:
                id_to_tenant[portable_id] = record["tenant_portable_id"]
    return by_section, id_to_section, id_to_tenant


def _same_tenant(id_to_tenant: dict[str, str], owner: dict, field: str, target_id: str | None) -> None:
    if not target_id:
        return
    _require(target_id in id_to_tenant, f"{field} references unknown record")
    _require(owner["tenant_portable_id"] == id_to_tenant[target_id], f"{field} crosses tenant boundary")


def _money_times_quantity(unit_price_cents: int, quantity_decimal: str) -> int:
    value = Decimal(unit_price_cents) * Decimal(quantity_decimal)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _validate_secret_keys(package: dict[str, Any]) -> None:
    for path, key, _child in _walk(package):
        lowered = key.lower()
        if lowered in {"contains_secrets", "secret_material_included"}:
            continue
        _require(
            not any(forbidden in lowered for forbidden in FORBIDDEN_SECRET_KEYS),
            f"forbidden secret-like key {key!r} at {path}",
        )


def _validate_date_values(package: dict[str, Any]) -> None:
    date_keys = {"document_date", "due_date", "expires_at", "follow_up_at"}
    datetime_keys = {
        "exported_at_utc",
        "scheduled_start_at",
        "released_at",
        "started_at",
        "ready_at",
        "completed_at",
        "reopened_at",
        "cancelled_at",
        "start_at",
        "end_at",
        "due_at",
        "created_at",
        "occurred_at",
    }
    for path, key, child in _walk(package):
        if child is None:
            continue
        if key in date_keys:
            try:
                date.fromisoformat(str(child))
            except ValueError as exc:
                raise ValidationError(f"malformed date at {path}.{key}") from exc
        if key in datetime_keys:
            try:
                datetime.fromisoformat(str(child).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValidationError(f"malformed date-time at {path}.{key}") from exc


def _validate_manifest(package: dict[str, Any], by_section: dict[str, dict[str, dict]]) -> None:
    manifest = package["manifest"]
    counts = manifest["entity_counts"]
    for section in SECTIONS:
        _require(counts[section] == len(package[section]), f"manifest entity_counts.{section} mismatch")

    source_tenant = manifest["source_tenant_portable_id"]
    _require(source_tenant in by_section["tenants"], "manifest source_tenant_portable_id is unknown")
    tenant = by_section["tenants"][source_tenant]
    _require(manifest["shop_timezone"] == tenant["timezone"], "manifest shop_timezone must match source tenant")
    _require(manifest["currency"] == tenant["currency"], "manifest currency must match source tenant")
    _require(manifest["locale"] == tenant["locale"], "manifest locale must match source tenant")

    _require(manifest["attachment_count"] == len(package["attachments"]), "manifest attachment_count mismatch")
    _require(manifest["attachment_bytes"] == sum(item["size_bytes"] for item in package["attachments"]), "manifest attachment_bytes mismatch")
    _require(len(manifest["file_inventory"]) == len(package["attachments"]), "manifest file_inventory count mismatch")


def _validate_relationships(package: dict[str, Any], by_section: dict[str, dict[str, dict]], id_to_section: dict[str, str], id_to_tenant: dict[str, str]) -> None:
    tenant_ids = set(by_section["tenants"])
    for section in SECTIONS:
        if section == "tenants":
            continue
        for record in package[section]:
            _require(record["tenant_portable_id"] in tenant_ids, f"{section} references unknown tenant")

    for user in package["users"]:
        _same_tenant(id_to_tenant, user, "user.tenant_portable_id", user["tenant_portable_id"])

    for customer in package["customers"]:
        _same_tenant(id_to_tenant, customer, "customer.tenant_portable_id", customer["tenant_portable_id"])

    for estimate in package["estimates"]:
        _require(estimate["customer_portable_id"] in by_section["customers"], "estimate references wrong source type for customer")
        _same_tenant(id_to_tenant, estimate, "estimate.customer_portable_id", estimate["customer_portable_id"])
        converted = estimate.get("converted_order_portable_id")
        if converted:
            _require(converted in by_section["orders"], "estimate converted_order_portable_id references wrong source type")
            _same_tenant(id_to_tenant, estimate, "estimate.converted_order_portable_id", converted)

    for item in package["estimate_items"]:
        _require(item["estimate_portable_id"] in by_section["estimates"], "estimate item references wrong source type")
        _same_tenant(id_to_tenant, item, "estimate_item.estimate_portable_id", item["estimate_portable_id"])
        _same_tenant(id_to_tenant, item, "estimate_item.assigned_user_portable_id", item.get("assigned_user_portable_id"))
        if item.get("assigned_user_portable_id"):
            _require(item["assigned_user_portable_id"] in by_section["users"], "estimate item assigned_user_portable_id references wrong source type")

    for order in package["orders"]:
        _require(order["customer_portable_id"] in by_section["customers"], "order references wrong source type for customer")
        _same_tenant(id_to_tenant, order, "order.customer_portable_id", order["customer_portable_id"])
        source = order.get("source_estimate_portable_id")
        if source:
            _require(source in by_section["estimates"], "order source_estimate_portable_id references wrong source type")
            _same_tenant(id_to_tenant, order, "order.source_estimate_portable_id", source)

    for item in package["order_items"]:
        _require(item["order_portable_id"] in by_section["orders"], "order item references wrong source type")
        _same_tenant(id_to_tenant, item, "order_item.order_portable_id", item["order_portable_id"])
        _same_tenant(id_to_tenant, item, "order_item.assigned_user_portable_id", item.get("assigned_user_portable_id"))
        if item.get("assigned_user_portable_id"):
            _require(item["assigned_user_portable_id"] in by_section["users"], "order item assigned_user_portable_id references wrong source type")
        source = item.get("source_estimate_item_portable_id")
        if source:
            _require(source in by_section["estimate_items"], "order item source_estimate_item_portable_id references wrong source type")
            _same_tenant(id_to_tenant, item, "order_item.source_estimate_item_portable_id", source)

    for work_order in package["work_orders"]:
        _require(work_order["order_portable_id"] in by_section["orders"], "work order references wrong source type for order")
        _require(work_order["customer_portable_id"] in by_section["customers"], "work order references wrong source type for customer")
        _same_tenant(id_to_tenant, work_order, "work_order.order_portable_id", work_order["order_portable_id"])
        _same_tenant(id_to_tenant, work_order, "work_order.customer_portable_id", work_order["customer_portable_id"])
        for user_id in work_order["assigned_user_portable_ids"]:
            _require(user_id in by_section["users"], "work order assigned_user_portable_ids references wrong source type")
            _same_tenant(id_to_tenant, work_order, "work_order.assigned_user_portable_ids", user_id)
        for snapshot in work_order["items_snapshot"]:
            item_id = snapshot["order_item_portable_id"]
            _require(item_id in by_section["order_items"], "work order item snapshot references wrong source type")
            _same_tenant(id_to_tenant, work_order, "work_order.items_snapshot.order_item_portable_id", item_id)
            _require(by_section["order_items"][item_id]["order_portable_id"] == work_order["order_portable_id"], "work order item snapshot references an item from another order")

    seen_invoice_orders: set[str] = set()
    for invoice in package["invoices"]:
        _require(invoice["order_portable_id"] in by_section["orders"], "invoice references wrong source type for order")
        _require(invoice["customer_portable_id"] in by_section["customers"], "invoice references wrong source type for customer")
        _same_tenant(id_to_tenant, invoice, "invoice.order_portable_id", invoice["order_portable_id"])
        _same_tenant(id_to_tenant, invoice, "invoice.customer_portable_id", invoice["customer_portable_id"])
        _require(invoice["order_portable_id"] not in seen_invoice_orders, "more than one invoice references an order")
        seen_invoice_orders.add(invoice["order_portable_id"])

    for event in package["calendar_events"]:
        if event.get("order_portable_id"):
            _require(event["order_portable_id"] in by_section["orders"], "calendar event order_portable_id references wrong source type")
            _same_tenant(id_to_tenant, event, "calendar_event.order_portable_id", event["order_portable_id"])
        if event.get("order_item_portable_id"):
            _require(event["order_item_portable_id"] in by_section["order_items"], "calendar event order_item_portable_id references wrong source type")
            _same_tenant(id_to_tenant, event, "calendar_event.order_item_portable_id", event["order_item_portable_id"])
        if event.get("assigned_user_portable_id"):
            _require(event["assigned_user_portable_id"] in by_section["users"], "calendar event assigned_user_portable_id references wrong source type")
            _same_tenant(id_to_tenant, event, "calendar_event.assigned_user_portable_id", event["assigned_user_portable_id"])
        _require(event["completion_affects_production"] is False, "calendar completion must remain separate from production completion")

    for section in ("reminders", "notes", "attachments", "audit_events"):
        for record in package[section]:
            source_type = record["source_type"] if section != "audit_events" else record["entity_type"]
            source_id = record["source_portable_id"] if section != "audit_events" else record["entity_portable_id"]
            expected_section = SOURCE_TYPE_TO_SECTION[source_type]
            _require(source_id in by_section[expected_section], f"{section} references wrong source type")
            _same_tenant(id_to_tenant, record, f"{section}.{source_type}", source_id)
            actor_id = record.get("author_user_portable_id") or record.get("actor_user_portable_id")
            if actor_id:
                _require(actor_id in by_section["users"], f"{section} actor/author references wrong source type")
                _same_tenant(id_to_tenant, record, f"{section}.actor_or_author", actor_id)


def _validate_totals(package: dict[str, Any]) -> None:
    estimate_items = defaultdict(list)
    for item in package["estimate_items"]:
        expected_line = _money_times_quantity(item["unit_price_cents"], item["quantity_decimal"])
        _require(item["line_total_cents"] == expected_line, "estimate item line_total_cents does not match unit price times quantity")
        estimate_items[item["estimate_portable_id"]].append(item)

    for estimate in package["estimates"]:
        subtotal = sum(item["line_total_cents"] for item in estimate_items[estimate["portable_id"]])
        _require(estimate["subtotal_cents"] == subtotal, "estimate subtotal_cents does not match estimate items")
        _require(estimate["total_cents"] == estimate["subtotal_cents"] - estimate["discount_cents"] + estimate["tax_cents"], "estimate total_cents invariant failed")
        if estimate["customer_tax_exempt_snapshot"]:
            _require(estimate["tax_cents"] == 0, "tax-exempt estimate must preserve zero tax")

    order_items = defaultdict(list)
    for item in package["order_items"]:
        expected_line = _money_times_quantity(item["unit_price_cents"], item["quantity_decimal"])
        _require(item["line_total_cents"] == expected_line, "order item line_total_cents does not match unit price times quantity")
        order_items[item["order_portable_id"]].append(item)

    for order in package["orders"]:
        subtotal = sum(item["line_total_cents"] for item in order_items[order["portable_id"]])
        _require(order["subtotal_cents"] == subtotal, "order subtotal_cents does not match order items")
        _require(order["total_cents"] == order["subtotal_cents"] - order["discount_cents"] + order["tax_cents"], "order total_cents invariant failed")
        if order["customer_tax_exempt_snapshot"]:
            _require(order["tax_cents"] == 0, "tax-exempt order must preserve zero tax")

    for invoice in package["invoices"]:
        _require(invoice["total_cents"] == invoice["subtotal_cents"] - invoice["discount_cents"] + invoice["tax_cents"], "invoice total_cents invariant failed")
        _require(invoice["balance_due_cents"] == invoice["total_cents"] - invoice["amount_paid_cents"], "invoice balance_due_cents invariant failed")
        if invoice["customer_tax_exempt_snapshot"]:
            _require(invoice["tax_cents"] == 0, "tax-exempt invoice must preserve zero tax")


def _validate_files(package: dict[str, Any]) -> None:
    inventory = {item["path"]: item for item in package["manifest"]["file_inventory"]}
    _require(len(inventory) == len(package["manifest"]["file_inventory"]), "manifest file_inventory contains duplicate paths")
    for attachment in package["attachments"]:
        path = attachment["file_inventory_path"]
        _require(".." not in path and not path.startswith(("/", "\\")), "attachment file_inventory_path must be package-relative")
        _require(path in inventory, "attachment missing from manifest file_inventory")
        item = inventory[path]
        _require(item["media_type"] == attachment["media_type"], "file inventory media_type mismatch")
        _require(item["size_bytes"] == attachment["size_bytes"], "file inventory size_bytes mismatch")
        _require(item["sha256"] == attachment["sha256"], "file inventory sha256 mismatch")


def validate_package(package: dict[str, Any]) -> list[str]:
    validate_json_schema(package)
    _validate_secret_keys(package)
    _validate_date_values(package)
    by_section, id_to_section, id_to_tenant = _collect_records(package)
    _validate_manifest(package, by_section)
    _validate_relationships(package, by_section, id_to_section, id_to_tenant)
    _validate_totals(package)
    _validate_files(package)
    return ["json schema valid", "semantic package valid"]


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
