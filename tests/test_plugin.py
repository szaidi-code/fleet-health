#!/usr/bin/env python3
"""
Unit tests for Fleet DM Health Plugin.
Tests manifest schema, CLI commands, demo data generation, and osquery report format.
"""

import unittest
import subprocess
import json
import os
import re
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

class TestFleetPlugin(unittest.TestCase):
    def test_manifest_schema(self):
        manifest_path = PLUGIN_DIR / "manifest.json"
        self.assertTrue(manifest_path.is_file(), "manifest.json must exist")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("schemaVersion"), 1)
        self.assertEqual(manifest.get("id"), "fleet.health")
        self.assertEqual(manifest.get("author"), "szaidi-code")
        self.assertEqual(manifest.get("license"), "MIT")
        self.assertIn("bar-widget", manifest.get("kinds", []))
        self.assertIn("barWidget", manifest.get("entryPoints", {}))

        widget_entry = PLUGIN_DIR / manifest["entryPoints"]["barWidget"]
        self.assertTrue(widget_entry.is_file(), f"Entry point {widget_entry} must exist")

    def test_omarchy_plugin_validate(self):
        res = subprocess.run(["omarchy", "plugin", "validate", str(PLUGIN_DIR)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"omarchy plugin validate failed: {res.stderr}")

    def test_demo_report_structure(self):
        report_bin = PLUGIN_DIR / "bin" / "omarchy-fleet-health-report"
        self.assertTrue(report_bin.is_file(), "omarchy-fleet-health-report binary must exist")

        res = subprocess.run([str(report_bin), "--demo"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"omarchy-fleet-health-report --demo failed: {res.stderr}")

        data = json.loads(res.stdout)
        self.assertTrue(data.get("connected"))
        self.assertIn("server_url", data)
        self.assertNotIn("192.168", data["server_url"], "Demo mode must not leak private IP")

        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_nodes"), 4)
        self.assertEqual(summary.get("online_nodes"), 4)
        self.assertEqual(summary.get("status"), "Healthy")
        self.assertGreater(summary.get("total_ram_gb", 0), 0)

        nodes = data.get("nodes", [])
        self.assertEqual(len(nodes), 4)

        for node in nodes:
            self.assertIn("id", node)
            self.assertIn("hostname", node)
            self.assertIn("ip", node)
            self.assertNotIn("192.168", node["ip"], "Demo mode node IP must not leak private IP")
            self.assertIn("cpu", node)
            self.assertIn("load_1m", node["cpu"])
            self.assertIn("memory", node)
            self.assertIn("total_mb", node["memory"])
            self.assertIn("used_mb", node["memory"])
            self.assertIn("kernel", node)
            self.assertIn("version", node["kernel"])
            self.assertIn("uptime_human", node["kernel"])

    def test_status_script(self):
        status_bin = PLUGIN_DIR / "bin" / "omarchy-fleet-status"
        self.assertTrue(status_bin.is_file(), "omarchy-fleet-status binary must exist")

        res = subprocess.run([str(status_bin)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"omarchy-fleet-status failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertIn("connected", data)
        self.assertIn("total_hosts", data)

if __name__ == "__main__":
    unittest.main()
