#!/usr/bin/env python3
"""
Security Gate - Aggregates security scan results and enforces policy

This script reads all security scan reports and makes a pass/fail decision
based on configured policy. It runs as the final gate before deployment.

Usage:
    python3 security/security_gate.py --enforce=true
    ENFORCE_SECURITY=true python3 security/security_gate.py
"""

import json
import os
import sys
import argparse
from pathlib import Path


class SecurityGate:
    def __init__(self, enforce=False):
        self.enforce = enforce
        self.results = {}
        self.passed = True
        self.failures = []

    def check_bandit(self):
        """Check Bandit SAST report for security issues"""
        report_path = "reports/bandit-report.json"
        if not os.path.exists(report_path):
            print("⚠️  Bandit report not found")
            return

        try:
            with open(report_path) as f:
                data = json.load(f)

            # Count issues by severity
            results = data.get("results", [])
            high_count = sum(1 for r in results if r.get("severity") == "HIGH")
            medium_count = sum(1 for r in results if r.get("severity") == "MEDIUM")

            self.results['bandit'] = {
                'high': high_count,
                'medium': medium_count,
                'total': len(results),
                'status': 'pass' if high_count == 0 else 'fail'
            }

            # Fail on HIGH findings
            if high_count > 0:
                self.failures.append(f"Bandit: {high_count} HIGH severity findings")
                self.passed = False

            print(f"✅ Bandit: {high_count} HIGH, {medium_count} MEDIUM")
        except Exception as e:
            print(f"❌ Error reading Bandit report: {e}")
            self.passed = False

    def check_semgrep(self):
        """Check Semgrep SAST report"""
        report_path = "reports/semgrep-report.json"
        if not os.path.exists(report_path):
            print("⚠️  Semgrep report not found")
            return

        try:
            with open(report_path) as f:
                data = json.load(f)

            results = data.get("results", [])
            errors = data.get("errors", [])

            self.results['semgrep'] = {
                'findings': len(results),
                'errors': len(errors),
                'status': 'pass' if len(results) == 0 and len(errors) == 0 else 'fail'
            }

            # Fail on any findings or errors
            if len(results) > 0 or len(errors) > 0:
                self.failures.append(f"Semgrep: {len(results)} findings, {len(errors)} errors")
                self.passed = False

            print(f"✅ Semgrep: {len(results)} findings, {len(errors)} errors")
        except Exception as e:
            print(f"❌ Error reading Semgrep report: {e}")
            self.passed = False

    def check_secrets(self):
        """Check gitleaks secret scanning report"""
        report_path = "reports/gitleaks-report.json"
        if not os.path.exists(report_path):
            print("⚠️  Gitleaks report not found (skipping)")
            return

        try:
            with open(report_path) as f:
                data = json.load(f)

            # gitleaks returns array of findings
            findings = len(data) if isinstance(data, list) else 0

            self.results['gitleaks'] = {
                'secrets_found': findings,
                'status': 'pass' if findings == 0 else 'fail'
            }

            # Fail on any secrets found
            if findings > 0:
                self.failures.append(f"Gitleaks: {findings} secrets detected in repository")
                self.passed = False

            print(f"✅ Gitleaks: {findings} secrets")
        except Exception as e:
            print(f"⚠️  Gitleaks report error (may not be run): {e}")

    def check_trivy(self):
        """Check Trivy container scan report for vulnerabilities"""
        report_path = "reports/trivy-report.json"
        if not os.path.exists(report_path):
            print("⚠️  Trivy report not found")
            return

        try:
            with open(report_path) as f:
                data = json.load(f)

            # Count vulnerabilities by severity
            results = data.get("Results", [])
            critical = 0
            high = 0

            for result in results:
                vulns = result.get("Vulnerabilities", [])
                for vuln in vulns:
                    severity = vuln.get("Severity", "")
                    if severity == "CRITICAL":
                        critical += 1
                    elif severity == "HIGH":
                        high += 1

            self.results['trivy'] = {
                'critical': critical,
                'high': high,
                'status': 'pass' if critical == 0 else 'fail'
            }

            # Fail on CRITICAL vulnerabilities
            if critical > 0:
                self.failures.append(f"Trivy: {critical} CRITICAL vulnerabilities in container")
                self.passed = False

            print(f"✅ Trivy: {critical} CRITICAL, {high} HIGH")
        except Exception as e:
            print(f"❌ Error reading Trivy report: {e}")
            self.passed = False

    def check_dependency_check(self):
        """Check OWASP Dependency-Check report for vulnerable dependencies"""
        report_path = "reports/dependency-check-report.json"
        if not os.path.exists(report_path):
            print("⚠️  Dependency-Check report not found")
            return

        try:
            with open(report_path) as f:
                data = json.load(f)

            vulns = data.get("reportSchema", {}).get("vulnerabilities", [])

            # Count by severity
            critical = sum(1 for v in vulns if v.get("cvssv3", {}).get("baseSeverity") == "CRITICAL")
            high = sum(1 for v in vulns if v.get("cvssv3", {}).get("baseSeverity") == "HIGH")

            self.results['dependency-check'] = {
                'critical': critical,
                'high': high,
                'total': len(vulns),
                'status': 'pass' if critical == 0 else 'fail'
            }

            # Fail on CRITICAL vulnerabilities
            if critical > 0:
                self.failures.append(f"Dependency-Check: {critical} CRITICAL vulnerable dependencies")
                self.passed = False

            print(f"✅ Dependency-Check: {critical} CRITICAL, {high} HIGH, {len(vulns)} total")
        except Exception as e:
            print(f"⚠️  Dependency-Check report error (may not be run): {e}")

    def run_all_checks(self):
        """Run all security checks in sequence"""
        print("\n" + "="*60)
        print("🔒 SECURITY GATE - Evaluating scan results")
        print("="*60 + "\n")

        self.check_bandit()
        self.check_semgrep()
        self.check_secrets()
        self.check_trivy()
        self.check_dependency_check()

        # Print summary
        print("\n" + "="*60)
        print("SECURITY GATE SUMMARY")
        print("="*60)
        print(json.dumps(self.results, indent=2))
        print("="*60)

        # Print failures
        if self.failures:
            print("\n⚠️  SECURITY ISSUES DETECTED:")
            for i, failure in enumerate(self.failures, 1):
                print(f"  {i}. {failure}")

        return self.get_status()

    def get_status(self):
        """Determine gate status based on policy and enforcement flag"""
        if not self.passed:
            if self.enforce:
                print("\n❌ SECURITY GATE: FAIL (enforcement enabled)")
                print("   Pipeline will be stopped due to security issues.")
                return False
            else:
                print("\n⚠️  SECURITY GATE: FAIL (enforcement disabled)")
                print("   Security issues detected but enforcement is OFF.")
                print("   Pipeline continues in advisory mode.")
                return True
        else:
            print("\n✅ SECURITY GATE: PASS")
            print("   All security checks passed.")
            return True


def main():
    parser = argparse.ArgumentParser(
        description='Security Gate - Enforce security policy before deployment'
    )
    parser.add_argument(
        '--enforce',
        type=str,
        default='false',
        help='Enforce security gate (true/false). Default: false'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Parse enforce flag from argument
    enforce = args.enforce.lower() in ['true', '1', 'yes']

    # Allow ENFORCE_SECURITY environment variable to override
    if os.environ.get('ENFORCE_SECURITY', '').lower() in ['true', '1', 'yes']:
        enforce = True

    if args.verbose:
        print(f"ℹ️  Enforce mode: {enforce}")
        print(f"ℹ️  Reports directory: reports/")
        print(f"ℹ️  Looking for: bandit-report.json, semgrep-report.json, etc.\n")

    # Run the security gate
    gate = SecurityGate(enforce=enforce)
    passed = gate.run_all_checks()

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
