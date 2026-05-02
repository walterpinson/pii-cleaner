# pii-cleaner

A CLI tool for redacting Personally Identifiable Information (PII) from CSV and PDF bank/credit card statements.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/walterpinson/pii-cleaner.git
cd pii-cleaner
uv sync
```

This installs all dependencies, including the spaCy NLP model required for entity detection.

### As a package

```bash
pip install pii-cleaner
```

## Usage

All commands default to **dry-run mode** — no files are written unless you pass `--apply`.

### Redact a single file

```bash
pii-cleaner redact file path/to/statement.csv
pii-cleaner redact file path/to/statement.pdf
```

Write the redacted output (disable dry-run):

```bash
pii-cleaner redact file path/to/statement.csv --apply
```

Specify a custom output path:

```bash
pii-cleaner redact file path/to/statement.csv --output path/to/redacted.csv --apply
```

### Redact all files in a folder

```bash
pii-cleaner redact folder path/to/statements/
```

Process subdirectories recursively and write output:

```bash
pii-cleaner redact folder path/to/statements/ --recursive --apply
```

Write output to a specific directory:

```bash
pii-cleaner redact folder path/to/statements/ --output path/to/output/ --apply
```

### Preview redaction changes

Inspect what would be changed without writing any files:

```bash
pii-cleaner preview path/to/statement.csv
pii-cleaner preview path/to/statement.pdf --lines 30
```

### Validate a configuration file

```bash
pii-cleaner validate-config path/to/config.yaml
```

### View a saved run report

```bash
pii-cleaner report path/to/report_abc12345.json
```

### Global options

| Option | Description |
|---|---|
| `--version` | Show version and exit |
| `--verbose` / `-v` | Enable verbose debug logging |

## Configuration

All settings are optional. By default, pii-cleaner uses built-in defaults with no config file.

Pass a custom config with `--config` / `-c`:

```bash
pii-cleaner redact file statement.csv --config config.yaml --apply
```

See [`examples/config.yaml`](examples/config.yaml) for a fully documented example, and [`examples/advanced_config.yaml`](examples/advanced_config.yaml) for a more complete configuration.

### Key configuration options

```yaml
# Confidence threshold for PII detection (0.0–1.0)
confidence_threshold: 0.5

# Always create a JSON audit report alongside output files
create_audit_report: true

# Known names/entities to always redact
identities:
  - "Jane Q. Public"
  - "Acme Financial LLC"

aliases:
  - "J. Q. Public"

# Custom regex patterns
custom_patterns:
  - name: "customer_id"
    regex: "\\bCUST-[0-9]{6}\\b"
    action: "replace"
    replacement: "[CUSTOMER_ID]"

# Financial field masking
financial_rules:
  account_number:
    preserve_last_n: 4
    mask_char: "X"
  card_number:
    preserve_last_n: 4
    mask_char: "X"

# CSV-specific settings
csv:
  sensitive_columns:
    - "ssn"
    - "tax_id"
  preserve_headers: true

# PDF output formats
pdf:
  output_formats:
    txt: true
    md: true
    json_report: true
    pdf: false

# File inclusion/exclusion globs
include_globs:
  - "*.csv"
  - "*.pdf"
exclude_globs:
  - "archive_*.csv"
```

## Development

Install dependencies (including dev tools):

```bash
uv sync
```

Run tests:

```bash
make test
# or
uv run pytest tests/ -v --tb=short
```

Lint:

```bash
make lint
# or
uv run ruff check pii_cleaner/ tests/
```

Format code:

```bash
make format
```

Run tests with coverage:

```bash
make test-cov
```

## License

MIT
