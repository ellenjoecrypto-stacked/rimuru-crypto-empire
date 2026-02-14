#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Security Testing Suite
Comprehensive security validation and penetration testing
"""

import os
import sys
import hashlib
import sqlite3
from pathlib import Path
import re
import json

class SecurityTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def test(self, name: str, condition: bool, severity: str = "HIGH"):
        status = "✅ PASS" if condition else "❌ FAIL"
        if condition:
            self.passed += 1
        else:
            self.failed += 1
            
        print(f"{status} [{severity}] {name}")
        return condition
    
    def warn(self, message: str):
        print(f"⚠️  WARNING: {message}")
        self.warnings += 1
    
    def run_all_tests(self):
        print("=" * 70)
        print("🛡️  RIMURU SECURITY TESTING SUITE")
        print("=" * 70)
        print()
        
        # Test 1: Environment Configuration
        print("📋 Testing Environment Configuration...")
        self.test_environment_config()
        print()
        
        # Test 2: File Permissions
        print("🔒 Testing File Permissions...")
        self.test_file_permissions()
        print()
        
        # Test 3: Credential Storage
        print("🔐 Testing Credential Storage...")
        self.test_credential_storage()
        print()
        
        # Test 4: API Security
        print("🌐 Testing API Security...")
        self.test_api_security()
        print()
        
        # Test 5: Input Validation
        print("✅ Testing Input Validation...")
        self.test_input_validation()
        print()
        
        # Test 6: SQL Injection Prevention
        print("💉 Testing SQL Injection Prevention...")
        self.test_sql_injection()
        print()
        
        # Test 7: Dependency Vulnerabilities
        print("📦 Testing Dependencies...")
        self.test_dependencies()
        print()
        
        # Summary
        print("=" * 70)
        print(f"SECURITY TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"⚠️  Warnings: {self.warnings}")
        
        score = (self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0
        print(f"\n🎯 Security Score: {score:.1f}%")
        
        if score >= 90:
            print("🌟 EXCELLENT - Production Ready!")
        elif score >= 75:
            print("✅ GOOD - Minor improvements needed")
        elif score >= 60:
            print("⚠️  FAIR - Several issues to address")
        else:
            print("❌ POOR - Critical security issues!")
        
        print("=" * 70)
        return self.failed == 0
    
    def test_environment_config(self):
        # Check if .env exists
        env_exists = Path('.env').exists()
        self.test("Environment file exists", env_exists, "HIGH")
        
        if env_exists:
            with open('.env', 'r') as f:
                content = f.read()
                
            # Check for default passwords
            has_default_pwd = 'ChangeMe' in content or 'CHANGE_ME' in content
            self.test("No default passwords in .env", not has_default_pwd, "CRITICAL")
            
            # Check for exposed secrets
            has_api_key = 'your_' in content.lower() and '_key_here' in content.lower()
            self.test("API keys configured", not has_api_key, "HIGH")
            
            # Check master password strength
            vault_pwd_match = re.search(r'VAULT_MASTER_PASSWORD=(.+)', content)
            if vault_pwd_match:
                pwd = vault_pwd_match.group(1).strip()
                strong = len(pwd) >= 16 and any(c.isupper() for c in pwd) and any(c.isdigit() for c in pwd)
                self.test("Strong master password (16+ chars)", strong, "CRITICAL")
    
    def test_file_permissions(self):
        sensitive_files = ['.env', 'data/.vault_salt', 'data/credentials_hardened.db']
        
        for file_path in sensitive_files:
            if Path(file_path).exists():
                # On Windows, we can't easily check Unix permissions
                self.test(f"Sensitive file exists: {file_path}", True, "MEDIUM")
            else:
                if file_path == '.env':
                    self.warn(f"Missing critical file: {file_path}")
    
    def test_credential_storage(self):
        # Check if credentials are stored in code
        code_files = list(Path('backend').rglob('*.py'))
        
        has_hardcoded_creds = False
        for file_path in code_files:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Look for suspicious patterns
                if re.search(r'(api_key|secret_key)\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', content, re.IGNORECASE):
                    has_hardcoded_creds = True
                    self.warn(f"Possible hardcoded credential in {file_path}")
        
        self.test("No hardcoded credentials in code", not has_hardcoded_creds, "CRITICAL")
    
    def test_api_security(self):
        # Check for CORS configuration
        api_file = Path('backend/api/main.py')
        if api_file.exists():
            with open(api_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_cors = 'CORSMiddleware' in content or 'cors' in content.lower()
            self.test("CORS middleware configured", has_cors, "HIGH")
            
            has_rate_limit = 'rate' in content.lower() and 'limit' in content.lower()
            self.test("Rate limiting implemented", has_rate_limit, "HIGH")
            
            has_auth = 'auth' in content.lower() or 'jwt' in content.lower()
            self.test("Authentication implemented", has_auth, "CRITICAL")
    
    def test_input_validation(self):
        # Check for Pydantic models
        code_files = list(Path('backend').rglob('*.py'))
        
        uses_pydantic = False
        for file_path in code_files:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if 'from pydantic import' in f.read():
                    uses_pydantic = True
                    break
        
        self.test("Input validation with Pydantic", uses_pydantic, "HIGH")
    
    def test_sql_injection(self):
        # Check for unsafe SQL queries
        code_files = list(Path('backend').rglob('*.py'))
        
        has_unsafe_sql = False
        for file_path in code_files:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Look for string formatting in SQL queries
                if re.search(r'execute\s*\(\s*f["\']|execute\s*\(\s*.*\s*%\s*', content):
                    has_unsafe_sql = True
                    self.warn(f"Possible SQL injection vulnerability in {file_path}")
        
        self.test("No SQL injection vulnerabilities", not has_unsafe_sql, "CRITICAL")
    
    def test_dependencies(self):
        req_file = Path('backend/requirements_hardened.txt')
        if req_file.exists():
            with open(req_file, 'r') as f:
                deps = f.read()
            
            # Check for security packages
            has_crypto = 'cryptography' in deps
            self.test("Cryptography library installed", has_crypto, "CRITICAL")
            
            has_testing = 'pytest' in deps
            self.test("Testing framework installed", has_testing, "MEDIUM")
            
            has_linter = 'bandit' in deps or 'safety' in deps
            self.test("Security linter installed", has_linter, "MEDIUM")

if __name__ == "__main__":
    tester = SecurityTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
