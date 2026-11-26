from copy import deepcopy
import json
import struct
import unittest
from unittest.mock import patch

from rdc_operator.common import KitError
from rdc_operator import windows


def ordinary_desktop():
    """Known ordinary-session facts, independent of the native API sequence."""
    return {
        "supported": True,
        "collector": {"pid": 100, "session_id": 3,
                      "token": {"integrity_rid": 0x2000, "elevated": False, "ui_access": False}},
        "desktop": {"window_station": {"name": "WinSta0", "visible": True},
                    "thread": {"name": "Default", "receives_input": True},
                    "input": {"name": "Default", "receives_input": True}},
        "foreground": {"window": 400, "window_after": 400, "stable": True},
        "target": {"window": 400, "exists": True, "pid": 200, "session_id": 3,
                   "identity_stable": True,
                   "token": {"integrity_rid": 0x2000, "ui_access": False}},
        "errors": [],
    }


class WindowsContextTests(unittest.TestCase):
    def assess(self, facts):
        before = deepcopy(facts)
        answer = windows.assess_windows_context(facts)
        self.assertEqual(facts, before, "Pure assessment must not mutate the evidence")
        self.assertFalse(answer["input_performed"])
        self.assertFalse(answer["permission_granted"])
        self.assertEqual(answer["uac_state"], "not_determined")
        return answer, {r["code"] for r in answer["risks"]}

    def test_same_integrity_is_an_observation_not_a_click_success(self):
        answer, codes = self.assess(ordinary_desktop())
        self.assertEqual(answer["status"], "observed")
        self.assertEqual(codes, set())
        self.assertNotIn("ready", answer)
        self.assertTrue(answer["limitations"])

    def test_same_integrity_cannot_overrule_a_different_session(self):
        facts = ordinary_desktop()
        facts["target"]["session_id"] = 4
        answer, codes = self.assess(facts)
        self.assertEqual(answer["status"], "blocked")
        self.assertIn("session_mismatch", codes)

    def test_uiaccess_is_not_a_higher_integrity_or_secure_desktop_pass(self):
        for uiaccess in (False, True):
            facts = ordinary_desktop()
            facts["collector"]["token"]["ui_access"] = uiaccess
            facts["target"]["token"]["integrity_rid"] = 0x3000
            answer, codes = self.assess(facts)
            self.assertEqual(answer["status"], "blocked")
            self.assertIn("higher_integrity_target", codes)
        facts = ordinary_desktop()
        facts["collector"]["token"]["ui_access"] = True
        facts["desktop"]["input"]["name"] = "Winlogon"
        answer, codes = self.assess(facts)
        self.assertEqual(answer["status"], "blocked")
        self.assertIn("protected_desktop_observed", codes)

    def test_access_denied_and_null_foreground_do_not_diagnose_uac(self):
        facts = ordinary_desktop()
        facts["desktop"]["input"] = {"name": None, "receives_input": None}
        facts["foreground"] = {"window": 0, "window_after": 0, "stable": True}
        facts["errors"] = [{"operation": "OpenInputDesktop", "winerror": 5}]
        answer, codes = self.assess(facts)
        self.assertEqual(answer["status"], "unknown")
        self.assertIn("desktop_unknown", codes)
        self.assertIn("foreground_unknown", codes)
        self.assertNotIn("uac_detected", codes)

    def test_unknown_token_is_not_assumed_to_match_the_collector(self):
        for where in ("collector", "target"):
            facts = ordinary_desktop()
            facts[where]["token"]["integrity_rid"] = None
            answer, codes = self.assess(facts)
            self.assertEqual(answer["status"], "unknown")
            self.assertIn(f"{where}_integrity_unknown", codes)

    def test_target_replacement_and_focus_drift_remain_visible(self):
        facts = ordinary_desktop()
        facts["target"]["identity_stable"] = False
        facts["foreground"] = {"window": 999, "window_after": 400, "stable": False}
        answer, codes = self.assess(facts)
        self.assertEqual(answer["status"], "blocked")
        self.assertIn("target_identity_changed", codes)
        self.assertIn("foreground_not_target", codes)
        self.assertIn("foreground_changed_or_unknown", codes)

    def test_existing_input_desktop_is_not_enough_without_a_target(self):
        facts = ordinary_desktop()
        facts["target"] = None
        answer, codes = self.assess(facts)
        self.assertEqual(answer["status"], "unknown")
        self.assertIn("target_not_provided", codes)

    def test_missing_window_is_a_diagnostic_not_fallback_target_selection(self):
        facts = ordinary_desktop()
        facts["target"] = {"window": 400, "exists": False, "identity_stable": False}
        answer, codes = self.assess(facts)
        self.assertEqual(answer["status"], "blocked")
        self.assertIn("window_not_found", codes)
        self.assertNotIn("target_identity_changed", codes)

    def test_non_windows_never_loads_or_calls_native_windows_code(self):
        with patch.object(windows.os, "name", "posix"), patch.object(windows, "_collect_windows_facts") as collect:
            answer = windows.inspect_windows_context()
        collect.assert_not_called()
        self.assertFalse(answer["supported"])
        self.assertEqual(answer["assessment"]["status"], "unsupported")
        json.dumps(answer, allow_nan=False)

    def test_invalid_handles_are_rejected_before_platform_or_native_queries(self):
        invalid = (True, False, 0, -1, 1.5, "400", [], 1 << (struct.calcsize("P") * 8))
        with patch.object(windows, "_collect_windows_facts") as collect:
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(KitError) as raised:
                    windows.inspect_windows_context(value)
                self.assertEqual(raised.exception.code, "invalid_arguments")
        collect.assert_not_called()

    def test_native_unavailability_preserves_unknown_evidence(self):
        with patch.object(windows.os, "name", "nt"), patch.object(windows, "_collect_windows_facts", side_effect=OSError("unavailable")):
            answer = windows.inspect_windows_context(400)
        self.assertTrue(answer["supported"])
        self.assertTrue(answer["read_only"])
        self.assertFalse(answer["atomic_snapshot"])
        self.assertEqual(answer["assessment"]["status"], "unknown")
        self.assertEqual(answer["errors"][0]["reason"], "native_api_unavailable")
        self.assertEqual(answer["requested_window"], 400)
        self.assertEqual(answer["target"]["window"], 400)
        self.assertNotIn("target_not_provided", {r["code"] for r in answer["assessment"]["risks"]})
        json.dumps(answer, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
