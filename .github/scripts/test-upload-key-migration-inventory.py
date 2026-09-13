#!/usr/bin/env python3
import json
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[2]
manifest_path = root / "generated/signing-central/android-upload-key-migration.json"

manifest = json.loads(manifest_path.read_text())

assert manifest["schema"] == 2
assert manifest["target_upload_certificate_sha1"] == "BCF2337D41E617C03BCAE698C09D1523654BD790"
assert manifest["target_upload_certificate_sha256"] == "7985BD6B33711BACA7E6BA722C2B3870EBBC802F7DB4A7BC1206BDAE51C4D5D6"
assert manifest["audited_at"] == "2026-09-13"

apps = manifest["apps"]
assert len(apps) == 22
assert len({app["package"] for app in apps}) == 22
assert all(app["status"] == "RESET_REQUIRED_NOW" for app in apps)
assert all(re.fullmatch(r"[0-9A-F]{40}", app["current_upload_certificate_sha1"]) for app in apps)
assert all(re.fullmatch(r"[0-9A-F]{64}", app["current_upload_certificate_sha256"]) for app in apps)
assert all(app["current_upload_certificate_sha1"] != manifest["target_upload_certificate_sha1"] for app in apps)

expected_packages = {
    "com.kamilunavo.kintaroq",
    "com.kamilunavo.maengelfix",
    "com.kamilunavo.onemoretap",
    "com.kamilunavo.schonerledigt",
    "de.kamilunav.kaltecalc",
    "de.kamilunavo.arbeitsklar",
    "de.kamilunavo.brennercalc",
    "de.kamilunavo.heizkorpercalc",
    "de.kamilunavo.hydrocalc",
    "de.kamilunavo.idlehandwerker",
    "de.kamilunavo.keepmeter",
    "de.kamilunavo.luftungscalc",
    "de.kamilunavo.magcalc",
    "de.kamilunavo.navopass",
    "de.kamilunavo.ninenine",
    "de.kamilunavo.rapportai",
    "de.kamilunavo.reklaio",
    "de.kamilunavo.rohrcalc",
    "de.kamilunavo.servicecheck",
    "de.kamilunavo.volumecalc",
    "de.kamilunavo.waermetakt",
    "de.kamilunavo.zweicheck",
}
assert {app["package"] for app in apps} == expected_packages

assert manifest["excluded_apps"] == [
    {
        "name": "NavoKids",
        "package": "com.kamilunavo.navokids",
        "reason": "Already correct and explicitly excluded from this migration",
    }
]
print("Upload-key migration inventory contract passed.")
