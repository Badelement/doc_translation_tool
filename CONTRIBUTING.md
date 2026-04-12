# Contributing to Document Translation Tool

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/doc_translation_tool.git
   cd doc_translation_tool
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Install Dependencies

```bash
cd source
python3 -m pip install -e ".[dev]"
```

### Configure for Development

```bash
cp .env.example .env
# Edit .env with your test API credentials
```

### Run the Application

```bash
python3 app.py
```

## Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use meaningful variable and function names
- Add docstrings to public functions and classes
- Keep functions focused and concise

### Type Hints

Use type hints for function parameters and return values:

```python
def translate_segment(text: str, direction: str) -> str:
    """Translate a text segment."""
    ...
```

## Testing

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=doc_translation_tool

# Run specific test file
pytest tests/test_translator.py
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test function names
- Include both positive and negative test cases

Example:

```python
def test_language_detection_chinese():
    """Test language detection for Chinese text."""
    result = detect_language("这是中文文本")
    assert result.language == "zh"
    assert result.is_confident
```

## Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Add tests** for new features
3. **Ensure all tests pass** before submitting
4. **Update CHANGELOG.md** with your changes
5. **Submit a pull request** with a clear description

### PR Title Format

Use conventional commit format:

- `feat: Add new feature`
- `fix: Fix bug in translation`
- `docs: Update documentation`
- `refactor: Refactor code structure`
- `test: Add tests`
- `chore: Update dependencies`

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Changes
- Change 1
- Change 2

## Testing
How to test these changes.

## Related Issues
Fixes #123
```

## Reporting Issues

### Bug Reports

Include:
- **Description**: Clear description of the bug
- **Steps to reproduce**: Detailed steps
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Environment**: OS, Python version, app version
- **Logs**: Relevant error messages or logs

### Feature Requests

Include:
- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other approaches considered

## Code Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, your PR will be merged

## Project Structure

```
doc_translation_tool/
├── source/
│   ├── doc_translation_tool/     # Main package
│   │   ├── core/                 # Core translation logic
│   │   ├── ui/                   # GUI components
│   │   ├── config/               # Configuration handling
│   │   └── utils/                # Utility functions
│   ├── tests/                    # Test suite
│   ├── scripts/                  # Build scripts
│   ├── docs/                     # Documentation
│   └── app.py                    # Application entry point
├── README.md                     # Project overview
├── LICENSE                       # License file
└── CONTRIBUTING.md               # This file
```

## Development Guidelines

### Adding New Features

1. **Discuss first**: Open an issue to discuss major changes
2. **Keep it focused**: One feature per PR
3. **Maintain compatibility**: Don't break existing functionality
4. **Document**: Update relevant documentation

### Fixing Bugs

1. **Reproduce**: Ensure you can reproduce the bug
2. **Add test**: Write a test that fails with the bug
3. **Fix**: Implement the fix
4. **Verify**: Ensure the test now passes

### Refactoring

1. **Preserve behavior**: Don't change functionality
2. **Add tests first**: Ensure existing behavior is tested
3. **Small steps**: Make incremental changes
4. **Explain why**: Document the reason for refactoring

## Commit Messages

Write clear, descriptive commit messages:

```
feat: Add support for PDF translation

- Implement PDF text extraction
- Add PDF-specific validation
- Update documentation

Closes #123
```

### Format

```
<type>: <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Release Process

Maintainers will handle releases:

1. Update version in `doc_translation_tool/__init__.py`
2. Update `CHANGELOG.md`
3. Create git tag
4. Build packages
5. Create GitHub release

## Questions?

- Open an issue for questions
- Check existing issues and documentation first
- Be respectful and constructive

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing! 🎉
