"""Generator contract tests; runnable without the backend or private CSVs."""
import csv
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.synth.generate import PRESETS, generate, write_csv
from scripts.synth.schema import DESCRIPTIONS, HEADERS, headers
from scripts.synth.validate import validate

ROOT = Path(__file__).resolve().parents[2]


class SynthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, **kwargs):
        out = self.root / "dataset"
        generate(out, **kwargs)
        return out

    def test_all_named_datasets_and_scenarios(self):
        for name, (day, clock, prefix, mode) in PRESETS.items():
            with self.subTest(name=name):
                out = self.root / name
                manifest = generate(out, day=date.fromisoformat(day), clock=time.fromisoformat(clock), prefix=prefix, mode=mode)
                report = validate(out)
                self.assertEqual(report["hospitals"], 12)
                self.assertEqual(report["physicians"], 21)
                self.assertEqual(report["duplicates"], 1)
                self.assertGreaterEqual(len(manifest["scenarios"]), 11)
                self.assertTrue(all(s["expected"] for s in manifest["scenarios"]))
                self.assertEqual(len(list(out.glob("snapshot_*.csv"))), 2)

    def test_same_seed_is_byte_identical_and_different_seed_changes_events(self):
        a, b, c = [self.root / name for name in ("a", "b", "c")]
        generate(a, seed=7)
        generate(b, seed=7)
        generate(c, seed=8)
        digest = lambda path: {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}
        self.assertEqual(digest(a), digest(b))
        self.assertNotEqual((a / "event_stream.csv").read_bytes(), (c / "event_stream.csv").read_bytes())

    def test_scale_multiplies_consults_and_lifecycle_events(self):
        counts = []
        for scale in (1, 10, 100):
            out = self.root / str(scale)
            generate(out, scale=scale)
            result = validate(out)
            counts.append(result)
        for scale, result in zip((1, 10, 100), counts):
            self.assertEqual(result["consults"], counts[0]["consults"] * scale)
            # 36 roster startup signals are fixed, not copied per consult.
            self.assertEqual(result["events"] - 36, (counts[0]["events"] - 36) * scale)
            self.assertEqual(result["duplicates"], scale)

    def test_schema_has_all_twenty_types(self):
        self.assertEqual(len(DESCRIPTIONS), 20)

    def test_supplied_headers_and_read_only_validation_when_available(self):
        private = ROOT / "data"
        if not (private / "event_stream.csv").exists():
            self.skipTest("protected source CSVs absent; generated schema validation still runs")
        with (private / "hospitals.csv").open(newline="", encoding="utf-8-sig") as handle:
            hospitals = [r["hospital_id"] for r in csv.DictReader(handle)]
        for name in HEADERS:
            path = private / (f"{name}_1820.csv" if name.startswith("snapshot_") else f"{name}.csv")
            with path.open(newline="", encoding="utf-8-sig") as handle:
                self.assertEqual(next(csv.reader(handle)), headers(name, hospitals))
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in private.glob("*.csv")}
        validate(private)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in private.glob("*.csv")})

    def test_cli_help_and_bad_arguments(self):
        script = str(ROOT / "scripts/synth/generate.py")
        result = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        for arguments in (["--scale", "2"], ["--prefix", "../bad"], ["--date", "2026-03-17"], ["--date", "2026-11-01", "--now", "01:20"]):
            result = subprocess.run([sys.executable, script, "--out", str(self.root / "bad"), *arguments], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error:", result.stderr)

    def test_outputs_do_not_overwrite_existing_files(self):
        (self.root / "event_stream.csv").write_text("keep this\n")
        with self.assertRaisesRegex(ValueError, "not owned"):
            generate(self.root)
        self.assertEqual((self.root / "event_stream.csv").read_text(), "keep this\n")
        with self.assertRaisesRegex(ValueError, "protected"):
            generate(ROOT / "data")

    def test_dst_uses_both_offsets(self):
        out = self.make(day=date(2026, 11, 1), clock=time(6, 20), mode="dst")
        with (out / "event_stream.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({datetime.fromisoformat(r["event_time"]).utcoffset().total_seconds() for r in rows}, {-14400, -18000})
        self.assertIn("dst_session", [s["name"] for s in json.loads((out / "manifest.json").read_text())["scenarios"]])

    def test_validator_rejects_causal_reference_and_duplicate_corruption(self):
        for corruption in ("unknown_reference", "before_receipt", "conflicting_duplicate", "missing_offset", "unsorted"):
            with self.subTest(corruption=corruption):
                out = self.make()
                path = out / "event_stream.csv"
                with path.open(newline="") as handle:
                    rows = list(csv.DictReader(handle))
                target = next(r for r in rows if r["event_type"] == "consult_triaged")
                if corruption == "unknown_reference":
                    target["physician_id"] = "unknown"
                elif corruption == "before_receipt":
                    target["consult_id"] = "missing-receipt"
                elif corruption == "conflicting_duplicate":
                    duplicate = next(r for r in rows if sum(r["event_id"] == x["event_id"] for x in rows) > 1)
                    duplicate["description"] = "conflict"
                elif corruption == "missing_offset":
                    target["event_time"] = "2026-04-07T12:00:00"
                else:
                    rows.reverse()
                write_csv(path, headers("event_stream"), rows)
                with self.assertRaises(ValueError):
                    validate(out)
                # Restore before the next case, including a valid hash manifest.
                generate(out)


if __name__ == "__main__":
    unittest.main()
