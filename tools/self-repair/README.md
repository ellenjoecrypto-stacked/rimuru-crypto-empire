# Rimuru Repair — Self-Learning Code Repair Tool

A comprehensive self-learning code quality scanner and auto-fixer for the Rimuru Crypto Empire repository. Modeled after the `RimuruAICore` self-learning architecture, it applies the same scan → detect → fix → verify → learn loop to **code quality** instead of trading.

## Features

- **Multi-language scanning** — Python, TypeScript/JavaScript, and config files
- **Auto-fix engine** — Applies safe, reversible fixes automatically
- **Self-learning** — Tracks which fixes stick vs. get reverted; stops applying fixes that are consistently reverted
- **Hot-file detection** — Prioritises files with historically high issue counts
- **Health score & report card** — 0-100 score with per-category breakdowns and trend tracking
- **GitHub Actions integration** — Runs on every push and weekly on a schedule

## Directory Structure

```
tools/self-repair/
├── __init__.py
├── rimuru_repair.py          # Main self-learning repair engine
├── config.yaml               # Scan rules, paths, thresholds
├── requirements.txt          # Tool dependencies
├── README.md                 # This file
├── scanners/
│   ├── python_scanner.py     # Python code quality scanner
│   ├── typescript_scanner.py # TypeScript/React scanner
│   └── config_scanner.py     # Config/env/path scanner
├── fixers/
│   ├── python_fixer.py       # Auto-fix Python issues
│   ├── typescript_fixer.py   # Auto-fix TypeScript issues
│   └── path_fixer.py         # Fix hardcoded paths
├── learning/
│   ├── pattern_memory.py     # Tracks recurring patterns & hot files
│   ├── fix_tracker.py        # Tracks fix success vs. revert rates
│   └── knowledge_base.json   # Persistent knowledge base
└── reports/
    └── health_report.py      # Generates repo health score/report card
```

## Usage

```bash
# Install dependencies
pip install -r tools/self-repair/requirements.txt

# Full scan + report (default)
python -m tools.self_repair.rimuru_repair --scan --report

# Scan + auto-fix
python -m tools.self_repair.rimuru_repair --scan --fix

# Just generate report from last scan
python -m tools.self_repair.rimuru_repair --report

# Scan a specific directory
python -m tools.self_repair.rimuru_repair --scan --path backend/

# Show learning statistics
python -m tools.self_repair.rimuru_repair --stats
```

## What Gets Scanned

### Python Files
| Issue | Severity | Auto-fixable |
|-------|----------|-------------|
| `print()` statements | Medium | ✅ → `logger.info()` |
| Bare `except:` | High | ✅ → `except Exception as e:` |
| `os.system()` calls | High | ✅ → `subprocess.run()` |
| Hardcoded file paths | Medium | ✅ → `os.getenv()` |
| `except: pass` | High | ✅ → log + continue |
| Mutable default args | High | ❌ manual |
| `import *` | Medium | ❌ manual |
| Debug code (`breakpoint`, `pdb`) | High | ❌ manual |
| Generic `except Exception` | Medium | ❌ manual |
| Missing docstrings | Low | ❌ manual |
| Missing type hints | Low | ❌ manual |
| TODO/FIXME/HACK comments | Low | ❌ tracked |

### TypeScript/JavaScript Files
| Issue | Severity | Auto-fixable |
|-------|----------|-------------|
| `console.log/error/warn` | Medium | ✅ removed |
| `: any` type usage | Medium | ✅ → `: unknown` |
| Hardcoded API URLs | High | ❌ manual |
| Empty catch blocks | High | ❌ manual |

### Config Files
| Issue | Severity | Auto-fixable |
|-------|----------|-------------|
| Hardcoded paths | Medium | ✅ |
| Potential hardcoded secrets | Critical | ❌ manual |
| Missing `.env.example` | Medium | ❌ manual |
| Missing `.gitignore` entries | High | ❌ manual |

## Self-Learning System

### Pattern Memory
Tracks how often each issue type appears in each file. Files with historically high issue counts are scanned first on subsequent runs.

### Fix Tracker
Records every fix applied (before/after, timestamp). On the next scan, verifies whether the fix is still in place. If a fix type has a revert rate above the configured threshold (`revert_threshold: 0.3` by default), it is flagged and auto-fixing is paused for that type.

### Knowledge Base
Persisted in `learning/knowledge_base.json`. Updated after every scan run with cumulative statistics, hot-file lists, and lessons learned from reverted fixes.

## Configuration

Edit `config.yaml` to customise:
- `exclude_dirs` — directories to skip
- `revert_threshold` — revert rate above which auto-fix is paused (0.0–1.0)
- `score_weights` — weights per health category
- `severity_weights` — score deduction per severity level

## Health Report Example

```
═══════════════════════════════════════════════════════
  RIMURU REPAIR — HEALTH REPORT
═══════════════════════════════════════════════════════
  Project: rimuru-crypto-empire
  Score:   78/100
  Grade:   B+
  Scanned: 2026-02-22 10:00 UTC
  Issues:  47 found  |  12 auto-fixed

  ✅ Logging               85.0% compliant  (3 issues)
  ✅ Error Handling        90.0% compliant  (2 issues)
  ⚠️  Hardcoded Paths       60.0% compliant  (8 issues)
  ✅ Type Safety           95.0% compliant  (1 issues)
  ✅ Security              92.0% compliant  (2 issues)
  ❌ Dead Code             45.0% compliant  (11 issues)

  Trend: ↑ Improving (+5 from last scan)

  Top Issue Files:
  1. deep_asset_hunt.py — 23 issues 🔥
  2. coinbase_check.py — 15 issues
  3. qrow/main.py — 12 issues
═══════════════════════════════════════════════════════
```
