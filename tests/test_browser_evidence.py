"""Offline data and CLI acceptance, without a browser or network connection."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from rdc_operator.browser_evidence import MAX_BUNDLE_BYTES, exit_code, validate_bundle


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "browser-evidence"
SCRIPT = ROOT / "scripts" / "verify_browser_evidence.py"


def load(name="counter-success"):
    return json.loads((FIXTURES / (name + ".json")).read_text(encoding="utf-8"))


class BrowserEvidenceTests(unittest.TestCase):
    def test_complete_synthetic_condition_has_explicit_proof_limits(self):
        result = validate_bundle(load())
        self.assertEqual(result["status"], "verified_fixture")
        self.assertEqual(exit_code(result), 0)
        self.assertTrue(result["business_condition_consistent"])
        self.assertFalse(result["authorization_verified"])
        self.assertFalse(result["authenticity_verified"])
        self.assertFalse(result["live_execution_verified"])
        self.assertFalse(result["automatic_replay_permitted"])
        self.assertEqual(result["pixel_freshness"], "unproven")
        self.assertFalse(result["artifact_checks"]["full_image_decode_verified"])

    def test_ack_echo_and_agent_verdict_cannot_replace_business_witness(self):
        for name in ("ack-without-effect", "echo-is-not-effect"):
            with self.subTest(name=name):
                result = validate_bundle(load(name))
                self.assertEqual(result["status"], "unverified")
                self.assertIn("business_witness_not_matching", result["reasons"])
        claim = load()
        claim["witness"]["source"] = "agent_report"
        self.assertEqual(validate_bundle(claim)["status"], "unverified")
        claim["witness"] = None
        self.assertIn("business_witness_missing", validate_bundle(claim)["reasons"])

    def test_lost_reply_remains_unknown_even_when_counter_has_changed(self):
        result = validate_bundle(load("lost-response"))
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertTrue(result["business_condition_consistent"])
        self.assertEqual(result["next_action"], "reconcile")
        self.assertFalse(result["automatic_replay_permitted"])
        self.assertEqual(exit_code(result), 1)

    def test_old_screen_and_reused_tab_are_rejected(self):
        for name in ("stale-screenshot", "reused-tab"):
            result = validate_bundle(load(name))
            self.assertEqual(result["status"], "unverified")
            self.assertIn("screenshot_page_identity_mismatch", result["reasons"])
        for field in ("context_id", "browser_id", "tab_id", "fixture_nonce", "origin"):
            changed = load()
            changed["witness"]["page"][field] = "http://different.invalid" if field == "origin" else "different-incarnation"
            result = validate_bundle(changed)
            self.assertIn("witness_page_identity_mismatch", result["reasons"])
            self.assertNotEqual(result["status"], "verified_fixture")

    def test_sequence_and_time_rollback_invalidate_observation(self):
        sequence = load()
        sequence["screenshot"]["sequence"] = sequence["observation"]["sequence"]
        self.assertIn("observation_sequence_not_increasing", validate_bundle(sequence)["reasons"])
        timing = load()
        timing["screenshot"]["capture_completed_at"] = "2026-11-25T00:00:00Z"
        self.assertIn("observation_time_order_mismatch", validate_bundle(timing)["reasons"])
        pixel_time = load()
        pixel_time["screenshot"]["captured_at"] = "2026-11-25T00:00:00Z"
        result = validate_bundle(pixel_time)
        self.assertIn("reported_pixel_time_outside_observation_interval", result["reasons"])
        self.assertNotEqual(result["pixel_freshness"], "verified")
        reference = load()
        reference["action"]["observation_id"] = "old-observation"
        self.assertIn("observation_reference_mismatch", validate_bundle(reference)["reasons"])

    def test_tampered_bytes_dimensions_or_request_do_not_pass(self):
        for field, value, expected in (("sha256", "0" * 64, "screenshot_hash_mismatch"),
                                       ("width", 3, "screenshot_dimensions_mismatch")):
            changed = load()
            changed["screenshot"][field] = value
            self.assertIn(expected, validate_bundle(changed)["reasons"])
        changed = load()
        changed["request"]["token"] = "different-token"
        self.assertIn("request_digest_mismatch", validate_bundle(changed)["reasons"])
        changed = load()
        changed["evidence_kind"] = "imported"
        result = validate_bundle(changed)
        self.assertEqual(result["status"], "unverified")
        self.assertIn("imported_evidence_has_no_authenticated_collector", result["reasons"])

    def test_stop_context_cannot_be_overridden_by_bundle_claims(self):
        claimed = load()
        claimed["host_allowed"] = True
        self.assertEqual(validate_bundle(claimed)["status"], "invalid")
        for flags in ({"host_refused": True}, {"operator_stopped": True}):
            result = validate_bundle(claimed, **flags)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["next_action"], "stop")
            self.assertFalse(result["authorization_verified"])

    def test_invalid_types_and_non_finite_values_return_invalid(self):
        for section, field, value in (("screenshot", "height", True), ("action", "dispatched", "yes"),
                                      ("observation", "sequence", float("nan")), ("screenshot", "png_base64", "!invalid!")):
            changed = load()
            changed[section][field] = value
            self.assertEqual(validate_bundle(changed)["status"], "invalid")
        changed = load()
        changed["executor"]["name"] = "x" * MAX_BUNDLE_BYTES
        self.assertEqual(validate_bundle(changed)["status"], "invalid")

    def test_cli_exit_codes_stdin_parser_and_no_output_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, expected in (("counter-success", 0), ("lost-response", 1), ("ack-without-effect", 1)):
                run = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURES / (name + ".json"))],
                                     cwd=tmp, capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, expected, run.stderr)
                self.assertEqual(json.loads(run.stdout)["verification_scope"], "offline_fixture_consistency_only")
            for raw in ('{"schema_version":1,"schema_version":2}', '{"x": NaN}'):
                run = subprocess.run([sys.executable, str(SCRIPT), "-"], input=raw,
                                     cwd=tmp, capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(json.loads(run.stdout)["status"], "invalid")
            # A stop does not even need to read the named file.
            run = subprocess.run([sys.executable, str(SCRIPT), "does-not-exist.json", "--host-refused"],
                                 cwd=tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(run.stdout)["status"], "blocked")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    @unittest.skipUnless(shutil.which("node"), "Node is only needed to syntax-check fixture JavaScript")
    def test_fixture_javascript_syntax_without_running_a_browser(self):
        html = (ROOT / "site" / "lab.html").read_text(encoding="utf-8")
        script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
        run = subprocess.run([shutil.which("node"), "--check"], input=script,
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
