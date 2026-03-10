# Agent Orchestration Platform - Test Suite

Comprehensive test suite for the Agent Orchestration Platform.

## Test Structure

```
tests/
├── unit/               # Unit tests (isolated component testing)
│   ├── test_agent_client.py      # SDK client tests
│   ├── test_triage_agent.py      # Triage agent tests
│   └── ...
├── integration/        # Integration tests (component interaction testing)
│   └── ...
├── fixtures/           # Shared test fixtures and helpers
│   └── ...
├── conftest.py         # Pytest configuration and global fixtures
└── README.md           # This file
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only async tests
pytest -m asyncio

# Run tests for a specific module
pytest tests/unit/test_agent_client.py

# Run a specific test
pytest tests/unit/test_agent_client.py::TestAgentClient::test_register_agent_success
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=sdk --cov=backend --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Fast (Skip Slow Tests)

```bash
pytest -m "not slow"
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, requires services)
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.asyncio` - Async tests

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.unit
@pytest.mark.asyncio
async def test_my_function(mock_openai_client):
    \"\"\"Test description.\"\"\"
    # Arrange
    client = MyClient()
    client.llm = mock_openai_client

    # Act
    result = await client.process_data({"input": "test"})

    # Assert
    assert result["output"] == "expected"
    mock_openai_client.chat.completions.create.assert_called_once()
```

### Integration Test Example

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_workflow(db_session, redis_client):
    \"\"\"Test complete workflow.\"\"\"
    # Test with real database and Redis connections
    pass
```

## Available Fixtures

### Database Fixtures

- `db_engine` - SQLite in-memory database engine
- `db_session` - Database session for testing

### Redis Fixtures

- `redis_client` - Fake Redis client (synchronous)
- `async_redis_client` - Fake Redis client (asynchronous)

### LLM Client Fixtures

- `mock_openai_client` - Mocked OpenAI client
- `mock_anthropic_client` - Mocked Anthropic client

### Data Fixtures

- `sample_ticket` - Sample support ticket
- `sample_agent_metadata` - Sample agent metadata

### Configuration Fixtures

- `test_settings` - Test environment settings

## Code Coverage Goals

- **Minimum coverage**: 70% (enforced by pytest)
- **Target coverage**: 85%+
- **Critical paths**: 95%+ (SDK client, routing logic, cost tracking)

## Continuous Integration

Tests run automatically on:
- Every push to main branch
- Every pull request
- Nightly builds

### CI Pipeline

```yaml
# .github/workflows/test.yml
- Install dependencies
- Run linters (black, isort, flake8, mypy)
- Run unit tests
- Run integration tests
- Upload coverage reports
- Build Docker images (if tests pass)
```

## Debugging Tests

### Run with PDB

```bash
pytest --pdb
```

### Run with Print Statements

```bash
pytest -s
```

### Run Last Failed Tests

```bash
pytest --lf
```

### Run with Full Traceback

```bash
pytest --tb=long
```

## Performance Testing

### Run with Duration Report

```bash
pytest --durations=10
```

Shows the 10 slowest tests.

## Test Data

Test data should be:
- **Deterministic** - Same input always produces same output
- **Isolated** - Tests don't depend on each other
- **Realistic** - Represents actual usage patterns
- **Minimal** - Only the data needed for the test

## Best Practices

1. **One Assert Per Test** (when possible)
   - Makes failures easier to debug
   - Each test has a single responsibility

2. **Use Descriptive Test Names**
   ```python
   # Good
   def test_register_agent_returns_uuid_when_successful():
       pass

   # Bad
   def test_register():
       pass
   ```

3. **Follow AAA Pattern**
   - **Arrange** - Set up test data and mocks
   - **Act** - Execute the code being tested
   - **Assert** - Verify the results

4. **Mock External Dependencies**
   - Don't make real API calls to OpenAI/Anthropic
   - Don't require external services to be running
   - Use fake/in-memory databases for unit tests

5. **Clean Up After Tests**
   - Use fixtures with `yield` for cleanup
   - Reset mocks between tests
   - Clear database/Redis after each test

## Troubleshooting

### Import Errors

If you see import errors, ensure the project root is in your Python path:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Async Test Failures

Make sure to:
1. Mark async tests with `@pytest.mark.asyncio`
2. Use `async def` for test functions
3. Use `await` for async calls

### Database Test Failures

- Check that tables are created in the test database
- Verify fixtures are cleaning up properly
- Ensure tests are isolated (no shared state)

### Coverage Not Including Files

Add the package to the coverage configuration in `pytest.ini`:

```ini
addopts =
    --cov=sdk
    --cov=backend
    --cov=examples
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

## Contributing

When adding new features:
1. Write tests first (TDD approach recommended)
2. Ensure all tests pass
3. Maintain coverage above 70%
4. Add integration tests for new workflows
5. Update this README if adding new test categories

---

**Questions?** Contact the team or open an issue on GitHub.
