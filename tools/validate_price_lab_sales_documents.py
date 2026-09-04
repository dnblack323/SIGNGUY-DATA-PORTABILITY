from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "price-lab-sales-documents-v1.schema.json"

PACKAGE_SECTIONS = [
    "customers",
    "projects",
    "documents",
    "revisions",
    "customerProjections",
    "brandingProfiles",
    "templates",
    "pdfOutputs",
    "assets",
]

FORBIDDEN_KEY_FRAGMENTS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "jwt",
    "credential",
    "connection_string",
    "sqlite_path",
    "database_path",
    "machine_path",
    "local_path",
}

ALLOWED_SAFETY_DECLARATION_KEYS = {
    "containssecrets",
    "includesrawdatabase",
    "includesmachinepaths",
}

PORTABLE_ID_RE = re.compile(r"^plsd_v1_[a-z][a-z0-9_]*_[0-9a-f]{12,64}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
MACHINE_PATH_RE = re.compile(r"(?i)(^[a-z]:[\\/]|^\\\\|^/(users|home|var|tmp|private|volumes)/)")
REVISION_TOTAL_CENT_FIELDS = (
    "subtotal_cents",
    "direct_invested_cost_cents",
    "fully_loaded_cost_cents",
    "profit_cents",
    "final_total_cents",
)
CUSTOMER_PROJECTION_FORBIDDEN_KEY_FRAGMENTS = (
    "internal",
    "directinvested",
    "fullyloaded",
    "profit",
    "margin",
    "pricingmethod",
    "sourceid",
    "sourcetype",
    "sourcesnapshot",
    "sourceevidence",
    "engine",
    "provenance",
    "assumption",
    "warning",
    "showthemath",
)


class ValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _canonical_bytes(package: dict[str, Any]) -> bytes:
    canonical = copy.deepcopy(package)
    canonical["manifest"]["contentSha256"] = "0" * 64
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(package: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(package)).hexdigest()


def validate_json_schema(package: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_schema(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(package), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "$" + "".join(f"[{part!r}]" if isinstance(part, int) else f".{part}" for part in first.path)
        raise ValidationError(f"schema validation failed at {location}: {first.message}")
    return ["json schema valid"]


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key, child
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _reject_nonfinite_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON number is not allowed: {value}")


def _load_package(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite_constant)


def _looks_like_machine_path(value: str) -> bool:
    stripped = value.strip()
    if MACHINE_PATH_RE.search(stripped):
        return True
    return re.search(r"(?i)\b[a-z]:[\\/](users|documents|windows|program files)\b", stripped) is not None


def _validate_no_forbidden_keys(package: dict[str, Any]) -> None:
    for path, key, child in _walk(package):
        normalized = _normalized_key(key)
        if normalized in ALLOWED_SAFETY_DECLARATION_KEYS:
            continue
        _require(
            not any(_normalized_key(fragment) in normalized for fragment in FORBIDDEN_KEY_FRAGMENTS),
            f"forbidden secret or path-like key {key!r} at {path}",
        )
        if isinstance(child, str) and _looks_like_machine_path(child):
            raise ValidationError(f"forbidden machine path value at {path}.{key}")


def _validate_dates(package: dict[str, Any]) -> None:
    for path, key, child in _walk(package):
        if child is None or not str(key).endswith(("Utc", "AtUtc")):
            continue
        try:
            datetime.fromisoformat(str(child).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(f"malformed date-time at {path}.{key}") from exc


def _ids_by_section(package: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    seen: dict[str, str] = {}
    by_section: dict[str, dict[str, dict[str, Any]]] = {}
    for section in PACKAGE_SECTIONS:
        by_section[section] = {}
        for index, record in enumerate(package[section]):
            portable_id = str(record.get("portableId") or "")
            _require(PORTABLE_ID_RE.fullmatch(portable_id) is not None, f"{section}[{index}] invalid portableId")
            _require(portable_id not in seen, f"duplicate portableId: {portable_id}")
            seen[portable_id] = section
            by_section[section][portable_id] = record
    return by_section


def _validate_manifest(package: dict[str, Any]) -> None:
    manifest = package["manifest"]
    counts = manifest["recordCounts"]
    for section in PACKAGE_SECTIONS:
        _require(counts[section] == len(package[section]), f"manifest recordCounts.{section} mismatch")
    compatibility = manifest["compatibility"]
    _require(compatibility["minimumPriceLabSchemaVersion"] <= compatibility["maximumPriceLabSchemaVersion"], "compatibility range is invalid")
    expected_hash = content_hash(package)
    _require(manifest["contentSha256"] == expected_hash, "manifest contentSha256 mismatch")


def _validate_assets(package: dict[str, Any], by_section: dict[str, dict[str, dict[str, Any]]]) -> None:
    asset_ids = set(by_section["assets"])
    for asset in package["assets"]:
        _require("/" not in asset["filename"] and "\\" not in asset["filename"] and ".." not in asset["filename"], "asset filename must be package-relative")
        try:
            raw = base64.b64decode(asset["dataBase64"], validate=True)
        except ValueError as exc:
            raise ValidationError("asset dataBase64 is invalid") from exc
        _require(len(raw) == asset["sizeBytes"], "asset sizeBytes mismatch")
        _require(hashlib.sha256(raw).hexdigest() == asset["sha256"], "asset sha256 mismatch")
    for branding in package["brandingProfiles"]:
        logo = branding.get("logo") if isinstance(branding.get("logo"), dict) else {}
        if logo.get("assetPortableId"):
            _require(logo["assetPortableId"] in asset_ids, "branding logo references unknown asset")
            asset = by_section["assets"][logo["assetPortableId"]]
            for logo_key, asset_key in (("fileName", "filename"), ("mimeType", "mimeType"), ("sizeBytes", "sizeBytes"), ("sha256", "sha256")):
                if logo_key in logo:
                    _require(logo[logo_key] == asset[asset_key], f"branding logo {logo_key} does not match asset")


def _validate_relationships(package: dict[str, Any], by_section: dict[str, dict[str, dict[str, Any]]]) -> None:
    customers = by_section["customers"]
    projects = by_section["projects"]
    documents = by_section["documents"]
    revisions = by_section["revisions"]
    projections = by_section["customerProjections"]
    branding = by_section["brandingProfiles"]
    templates = by_section["templates"]

    revision_numbers_by_document: dict[str, set[int]] = {}
    seen_projection_revisions: set[str] = set()

    for project in package["projects"]:
        customer_id = project["customerPortableId"]
        if customer_id is not None:
            _require(customer_id in customers, "project references unknown customer")

    def root_for(document_id: str) -> str:
        seen: set[str] = set()
        current_id = document_id
        while True:
            _require(current_id not in seen, "document conversion ancestry contains a cycle")
            seen.add(current_id)
            current = documents[current_id]
            source_id = current["sourceDocumentPortableId"]
            if source_id is None:
                _require(current["rootDocumentPortableId"] == current_id, "root document must identify itself")
                return current_id
            _require(source_id in documents, "document source ancestry is missing")
            current_id = source_id

    for document in package["documents"]:
        document_id = document["portableId"]
        if document["customerPortableId"] is not None:
            _require(document["customerPortableId"] in customers, "document references unknown customer")
        if document["projectPortableId"] is not None:
            _require(document["projectPortableId"] in projects, "document references unknown project")
            project_customer = projects[document["projectPortableId"]]["customerPortableId"]
            if document["customerPortableId"] is not None and project_customer is not None:
                _require(project_customer == document["customerPortableId"], "document and project customer references do not agree")
        source_document_id = document["sourceDocumentPortableId"]
        if source_document_id is not None:
            _require(source_document_id in documents, "document source ancestry is missing")
        current_revision_id = document["currentRevisionPortableId"]
        if document["status"] == "finalized":
            _require(current_revision_id is not None, "finalized document must identify a current revision")
        if current_revision_id is not None:
            _require(current_revision_id in revisions, "document current revision is missing")
            _require(revisions[current_revision_id]["documentPortableId"] == document_id, "document current revision belongs to another document")
        _require(document["rootDocumentPortableId"] in documents, "document root ancestry is missing")
        _require(root_for(document_id) == document["rootDocumentPortableId"], "document root ancestry does not match source chain")
        for ancestry in document["conversionPath"]:
            source = ancestry.get("sourceDocumentPortableId") or ancestry.get("sourceDocumentId")
            if source:
                _require(source in documents, "conversion ancestry references unknown document")

    for revision in package["revisions"]:
        document = documents.get(revision["documentPortableId"])
        _require(document is not None, "revision references unknown document")
        _require(revision["documentType"] == document["documentType"], "revision documentType mismatch")
        _require(revision["documentNumber"] == document["documentNumber"], "revision documentNumber mismatch")
        revisions_for_document = revision_numbers_by_document.setdefault(revision["documentPortableId"], set())
        _require(revision["revisionNumber"] not in revisions_for_document, "duplicate revision number within document")
        revisions_for_document.add(revision["revisionNumber"])

    for projection in package["customerProjections"]:
        document = documents.get(projection["documentPortableId"])
        revision = revisions.get(projection["revisionPortableId"])
        _require(document is not None, "customer projection references unknown document")
        _require(revision is not None, "customer projection references unknown revision")
        _require(revision["documentPortableId"] == projection["documentPortableId"], "customer projection revision belongs to another document")
        _require(projection["documentType"] == document["documentType"], "customer projection documentType mismatch")
        _require(projection["documentNumber"] == document["documentNumber"], "customer projection documentNumber mismatch")
        _require(projection["revisionPortableId"] not in seen_projection_revisions, "duplicate customer projection for revision")
        seen_projection_revisions.add(projection["revisionPortableId"])

    for template in package["templates"]:
        parent = template["parentTemplatePortableId"]
        if parent is not None:
            _require(parent in templates, "template parent is missing")

    def assert_template_acyclic(template_id: str) -> None:
        seen: set[str] = set()
        current_id: str | None = template_id
        while current_id is not None:
            _require(current_id not in seen, "template inheritance contains a cycle")
            seen.add(current_id)
            current_id = templates[current_id]["parentTemplatePortableId"]

    for template_id in templates:
        assert_template_acyclic(template_id)

    for pdf in package["pdfOutputs"]:
        document = documents.get(pdf["documentPortableId"])
        _require(document is not None, "pdf output references unknown document")
        if pdf["revisionPortableId"] is not None:
            _require(pdf["revisionPortableId"] in revisions, "pdf output references unknown revision")
            revision = revisions[pdf["revisionPortableId"]]
            _require(revision["documentPortableId"] == pdf["documentPortableId"], "pdf output revision belongs to another document")
            _require(pdf["documentType"] == document["documentType"], "pdf output documentType mismatch")
            _require(pdf["documentNumber"] == document["documentNumber"], "pdf output documentNumber mismatch")
        template = templates.get(pdf["templatePortableId"])
        branding_profile = branding.get(pdf["brandingProfilePortableId"])
        _require(template is not None, "pdf output references unknown template")
        _require(branding_profile is not None, "pdf output references unknown branding")
        _require(template["documentType"] == pdf["documentType"], "pdf output template documentType mismatch")
        _require(template["versionNumber"] == pdf["templateVersion"], "pdf output template version mismatch")
        _require(branding_profile["versionNumber"] == pdf["brandingVersion"], "pdf output branding version mismatch")
        _require("/" not in pdf["filename"] and "\\" not in pdf["filename"] and ".." not in pdf["filename"], "pdf filename must be package-relative")


def _validate_revision_totals(revision: dict[str, Any]) -> None:
    totals = revision["totals"]
    body = totals.get("totals") if isinstance(totals.get("totals"), dict) else None
    _require(body is not None, "revision totals must preserve engine totals")
    for field in REVISION_TOTAL_CENT_FIELDS:
        _require(isinstance(body.get(field), int), f"revision totals.{field} must be an integer number of cents")


def _validate_revision_engine_identity(revision: dict[str, Any]) -> None:
    _require(SHA256_RE.fullmatch(str(revision["engineWheelSha256"] or "")) is not None, "engineWheelSha256 must be a SHA-256 hex digest")
    engine = revision["sourceEvidence"].get("engine") if isinstance(revision["sourceEvidence"].get("engine"), dict) else {}
    if "engineVersion" in engine:
        _require(engine["engineVersion"] == revision["engineVersion"], "revision engineVersion does not match sourceEvidence.engine")
    if "engineSourceCommit" in engine:
        _require(engine["engineSourceCommit"] == revision["engineSourceCommit"], "revision engineSourceCommit does not match sourceEvidence.engine")
    for key in ("engineWheelSha256", "wheelSha256"):
        if key in engine:
            _require(str(engine[key]).lower() == str(revision["engineWheelSha256"]).lower(), "revision engineWheelSha256 does not match sourceEvidence.engine")


def _validate_customer_projection_safe(value: Any, path: str = "$.projection") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_key(key)
            _require(
                not any(fragment in normalized for fragment in CUSTOMER_PROJECTION_FORBIDDEN_KEY_FRAGMENTS),
                f"customer projection contains internal-only field {key!r} at {path}",
            )
            _validate_customer_projection_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_customer_projection_safe(child, f"{path}[{index}]")


def _validate_internal_evidence(package: dict[str, Any]) -> None:
    _require(package["manifest"]["containsInternalPricingInformation"] is True, "sales document package must declare internal pricing information")
    for revision in package["revisions"]:
        totals = revision["totals"]
        source_evidence = revision["sourceEvidence"]
        _require(isinstance(source_evidence.get("engine"), dict), "revision must preserve engine identity evidence")
        _require(isinstance(source_evidence.get("showTheMath"), dict), "revision must preserve Show the Math evidence")
        _validate_revision_totals(revision)
        _validate_revision_engine_identity(revision)
    for projection in package["customerProjections"]:
        projection_body = projection["projection"]
        _require(projection_body.get("view") == "customer", "customer projection must preserve customer-safe view marker")
        _validate_customer_projection_safe(projection_body)


def validate_package(package: dict[str, Any]) -> list[str]:
    validate_json_schema(package)
    _validate_no_forbidden_keys(package)
    _validate_dates(package)
    by_section = _ids_by_section(package)
    _validate_manifest(package)
    _validate_assets(package, by_section)
    _validate_relationships(package, by_section)
    _validate_internal_evidence(package)
    return ["json schema valid", "semantic sales document package valid"]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_price_lab_sales_documents.py <package.json>", file=sys.stderr)
        return 2
    try:
        package = _load_package(Path(argv[1]))
        for message in validate_package(package):
            print(message)
    except ValidationError as exc:
        print(f"package invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
