# Contributing to Rimuru Crypto Empire

Thank you for your interest in contributing to Rimuru Crypto Empire! This document provides guidelines and instructions for contributing to the project.

## 🎯 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Setup Development Environment

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/rimuru-crypto-empire.git
cd rimuru-crypto-empire
```

2. **Create a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

4. **Install pre-commit hooks**

```bash
pip install pre-commit
pre-commit install
```

5. **Copy environment file**

```bash
cp .env.example .env
# Edit .env with your configuration
```

## 📝 Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

Follow the coding standards below when making changes.

### 3. Run Linters and Formatters

**Python:**

```bash
# Check for issues
ruff check services/ backend/

# Auto-fix issues
ruff check services/ backend/ --fix

# Format code
ruff format services/ backend/

# Type checking
mypy services/shared/models.py --ignore-missing-imports
```

**Frontend:**

```bash
cd frontend

# Lint
npm run lint

# Fix linting issues
npm run lint:fix

# Format
npm run format

# Type check
npm run type-check
```

### 4. Test Your Changes

```bash
# Run Python tests
pytest tests/ -v

# Run specific test file
pytest tests/test_specific.py -v

# Run frontend tests
cd frontend && npm test
```

### 5. Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature"
# or
git commit -m "fix: resolve issue with..."
```

**Commit Message Convention:**

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## 🎨 Coding Standards

### Python

- **Python Version**: 3.11+
- **Linter**: Ruff (configured in `.ruff.toml`)
- **Formatter**: Ruff
- **Type Checker**: MyPy (configured in `pyproject.toml`)
- **Line Length**: 100 characters
- **Imports**: Sorted with isort (via ruff)
- **Quotes**: Double quotes for strings
- **Docstrings**: Google-style docstrings

**Example:**

```python
from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel


class TradingSignal(BaseModel):
    """Trading signal model.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        action: Action to take ("buy", "sell", "hold")
        confidence: Confidence score (0-1)
    """
    symbol: str
    action: str
    confidence: float
    
    def validate_signal(self) -> bool:
        """Validate the trading signal.
        
        Returns:
            True if signal is valid, False otherwise
        """
        return 0 <= self.confidence <= 1
```

### TypeScript/React

- **TypeScript Version**: 5.7+
- **Linter**: ESLint (configured in `frontend/.eslintrc.cjs`)
- **Formatter**: Prettier (configured in `frontend/.prettierrc.json`)
- **Style Guide**: React best practices
- **Quotes**: Single quotes for strings
- **Line Length**: 100 characters
- **Components**: Functional components with hooks

**Example:**

```typescript
import React, { useState, useEffect } from 'react';
import { Box, Typography } from '@mui/material';

interface TradingPanelProps {
  symbol: string;
  onTrade: (action: string) => void;
}

export const TradingPanel: React.FC<TradingPanelProps> = ({ symbol, onTrade }) => {
  const [price, setPrice] = useState<number>(0);

  useEffect(() => {
    // Fetch price logic
    fetchPrice(symbol).then(setPrice);
  }, [symbol]);

  return (
    <Box>
      <Typography variant="h6">{symbol}</Typography>
      <Typography>${price.toFixed(2)}</Typography>
    </Box>
  );
};
```

### General Guidelines

1. **Write clear, self-documenting code**
2. **Add comments for complex logic**
3. **Keep functions small and focused**
4. **Use meaningful variable names**
5. **Follow DRY (Don't Repeat Yourself)**
6. **Write tests for new features**
7. **Update documentation when needed**

## 🔒 Security Guidelines

### Never Commit Secrets

- **Never commit** API keys, passwords, or secrets
- Use environment variables for sensitive data
- Add sensitive files to `.gitignore`
- Use the credential vault for API keys

### Security Best Practices

1. **Input Validation**: Always validate user inputs
2. **SQL Injection**: Use parameterized queries
3. **XSS Prevention**: Properly escape output
4. **Authentication**: Implement proper auth checks
5. **Rate Limiting**: Add rate limiting to APIs
6. **Dependencies**: Keep dependencies updated
7. **Secrets**: Use environment variables or vault

### Reporting Security Issues

**Do not** create public issues for security vulnerabilities.

Instead:
1. Email the maintainer directly
2. Use GitHub's "Report a vulnerability" feature
3. Provide detailed information about the vulnerability

## 📚 Documentation

### Code Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings for Python
- Use JSDoc comments for TypeScript
- Keep documentation up-to-date with code changes

### README Updates

Update the README when:
- Adding new features
- Changing installation steps
- Updating prerequisites
- Adding new configuration options

## 🧪 Testing

### Writing Tests

**Python:**

```python
import pytest
from backend.core.rimuru_ai import RimuruAICore


def test_signal_generation():
    """Test AI signal generation."""
    ai = RimuruAICore()
    signal = ai.generate_signal("BTC/USDT")
    assert signal.confidence >= 0
    assert signal.confidence <= 1
```

**TypeScript:**

```typescript
import { render, screen } from '@testing-library/react';
import { TradingPanel } from './TradingPanel';

test('renders trading panel', () => {
  render(<TradingPanel symbol="BTC/USDT" onTrade={() => {}} />);
  expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
});
```

### Test Coverage

- Aim for >80% code coverage
- Test edge cases and error conditions
- Test both success and failure paths
- Use mocks for external dependencies

## 🐛 Bug Reports

When reporting bugs, include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Step-by-step instructions
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: OS, Python version, Node version
6. **Screenshots**: If applicable
7. **Logs**: Relevant error logs

## 💡 Feature Requests

When requesting features, include:

1. **Problem**: What problem does this solve?
2. **Solution**: Proposed solution
3. **Alternatives**: Alternative solutions considered
4. **Use Cases**: How would this be used?
5. **Benefits**: Benefits of this feature

## 🔍 Code Review Process

### For Contributors

- Respond to review comments promptly
- Be open to feedback and suggestions
- Update PR based on feedback
- Keep PRs focused and small

### For Reviewers

- Be constructive and respectful
- Focus on code quality and best practices
- Check for security issues
- Verify tests are included
- Test the changes locally if needed

## 📦 Pull Request Checklist

Before submitting a PR, ensure:

- [ ] Code follows project style guidelines
- [ ] All tests pass (`pytest tests/`)
- [ ] Linters pass (ruff, ESLint)
- [ ] Code is formatted (ruff format, prettier)
- [ ] Type checking passes (mypy)
- [ ] Documentation is updated
- [ ] Commit messages follow conventions
- [ ] Branch is up-to-date with main
- [ ] No merge conflicts
- [ ] Security vulnerabilities are addressed

## 🎓 Learning Resources

### Python

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

### TypeScript/React

- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/)
- [Material-UI Documentation](https://mui.com/)

### Docker

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## ❓ Questions?

- Check existing issues for similar questions
- Read the documentation in `/docs`
- Ask in GitHub Discussions
- Review closed PRs for examples

## 🙏 Thank You!

Thank you for contributing to Rimuru Crypto Empire! Your contributions help make this project better for everyone.

---

**Remember**: Quality over quantity. Small, well-tested PRs are better than large, untested ones.
