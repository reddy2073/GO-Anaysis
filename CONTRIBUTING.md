# Contributing to LegalDebateAI

Thank you for interest in contributing to LegalDebateAI! This document provides guidelines and instructions.

## Code of Conduct

- Be respectful and inclusive
- Focus on code quality and testing
- Document your changes
- Review existing tests before making changes

## Getting Started

### Prerequisites
- Python 3.10+
- Git
- API Keys for Anthropic (required), OpenAI/Gemini (optional)

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd LegalDebateAI

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run tests to verify setup
python test_scenarios.py
```

## Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes
- Write clean, documented code
- Follow existing code style
- Add type hints
- Include docstrings

### 3. Test Your Changes
```bash
# Run all tests
python test_scenarios.py

# Run system validation
python validate_system.py

# Test specific functionality (example)
python -c "from agents import expert_panel; print('OK')"
```

### 4. Commit & Push
```bash
git add .
git commit -m "feat: description of changes"
# or
git commit -m "fix: description of bug fix"
git push origin feature/your-feature-name
```

### 5. Create Pull Request
- Describe your changes clearly
- Reference any related issues
- Ensure all tests pass
- Wait for review

## Testing Guidelines

### All Changes Must Include Tests

For new features:
```python
def test_new_feature():
    """Test description"""
    # Setup
    # Test
    # Assert
    assert result is correct
```

### Running Tests

```bash
# All tests (should see 12/12 passing)
python test_scenarios.py

# Expected output:
# Results: 12/12 tests passed
```

### Test Coverage

Current coverage:
- Module imports: ✅
- Configuration: ✅
- Data processing: ✅
- Caching: ✅
- Database: ✅
- Debate agents: ✅
- Analysis modules: ✅

## Code Style

### Type Hints
```python
def argue(context: dict, round_num: int, opponent_arg: str = "") -> str:
    """Legal argument generation."""
    pass
```

### Docstrings
```python
def function_name(param: str) -> dict:
    """
    One-line summary.
    
    Longer description if needed.
    
    Args:
        param: Parameter description
        
    Returns:
        Return value description
        
    Raises:
        Exception: When this is raised
    """
    pass
```

### Error Handling
```python
try:
    result = some_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    # Fallback or re-raise
    raise
```

## Adding New Agents

### Template
```python
# agents/new_agent.py
"""New agent description."""

def run_agent(context: dict, *args) -> dict:
    """
    Run new agent analysis.
    
    Args:
        context: RAG context with legal documents
        
    Returns:
        dict: Analysis results
    """
    # Implementation
    return {
        "analysis": "...",
        "recommendations": [...],
    }
```

### Integration
1. Add to `agents/__init__.py`
2. Import in `debate_engine.py`
3. Add test in `test_scenarios.py`
4. Document in README.md

## Reporting Issues

### Bug Report Template
```
Title: [BUG] Short description

Description:
- What happened?
- What should happen?

Steps to Reproduce:
1. ...
2. ...
3. ...

Environment:
- Python version: 3.x
- OS: Windows/Linux/Mac
- Error message: ...
```

### Feature Request Template
```
Title: [FEATURE] Short description

Motivation:
Why is this needed?

Proposed Solution:
How should it work?

Examples:
Use case examples
```

## Performance Considerations

### Optimization Tips
- Use caching for repeated analyses (`use_cache=True`)
- Parallel execution for independent tasks
- Batch processing for multiple documents
- Local Ollama for offline inference

### Benchmarking
```python
import time

start = time.time()
result = run_debate(go_text, use_cache=False)
duration = time.time() - start
print(f"Duration: {duration:.2f}s")
```

## Documentation

### Update README.md for:
- New features
- Configuration changes
- API changes
- Performance improvements

### Code Comments
- Explain "why", not "what"
- Use docstrings for public functions
- Keep comments up to date

## Security

### API Keys
- Never commit `.env` or `config.py` with real keys
- Use environment variables
- Rotate keys regularly
- Use `.gitignore` for sensitive files

### Dependencies
- Review new dependencies carefully
- Use `pip freeze` for exact versions
- Update regularly for security patches

## Release Process

### Version Numbering
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

### Before Release
1. All tests passing (12/12)
2. Documentation updated
3. CHANGELOG updated
4. Version bumped in config.py

## Questions?

- Check existing issues and discussions
- Review code comments and docstrings
- Ask in pull request reviews
- Create a discussion issue

## Thank You!

Your contributions make LegalDebateAI better for everyone!

---

**Last Updated**: April 17, 2026
