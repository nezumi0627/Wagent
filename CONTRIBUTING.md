# Contributing to Wagent

Thank you for your interest in contributing to Wagent! 🎉

## Development Setup

1. Clone the repository
```bash
git clone https://github.com/nezumi0627/wagent.git
cd wagent
```

2. Install Rye (if not already installed)
```bash
curl -sSf https://rye.astral.sh/get | bash
```

3. Install dependencies
```bash
rye sync
```

4. Install Playwright browser
```bash
rye run playwright install chromium
```

## Running Tests

```bash
rye run pytest
```

## Code Style

We use Ruff for linting:
```bash
rye run ruff check wagent/
rye run ruff format wagent/
```

## Pull Request Guidelines

1. Create a feature branch from `main`
2. Make your changes
3. Run tests and linting
4. Submit a PR with a clear description

## Reporting Issues

Please include:
- Python version
- Operating system
- Steps to reproduce
- Error messages (if any)

## ⚠️ Important Notes

- **Do not include browser session data** (`browser_data/`) in commits
- **Test locally** before submitting PRs
- Keep changes focused and atomic
