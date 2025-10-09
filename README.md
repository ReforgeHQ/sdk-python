# reforge-python

Python client for reforge.com, providing Config, FeatureFlags as a Service

## Example usage

```python
from sdk_reforge import ReforgeSDK, Options
import sdk_reforge

options = Options(
    sdk_key="your-reforge-sdk-key"
)

context = {
  "user": {
    "team_id": 432,
    "id": 123,
    "subscription_level": 'pro',
    "email": "alice@example.com"
  }
}


sdk_reforge.set_options(options)

result = sdk_reforge.get_sdk().enabled("my-first-feature-flag", context=context)

print("my-first-feature-flag is:", result)
```

## Protocol Buffer Types

If you need to work with the underlying Protocol Buffer types, the following are re-exported for convenience:

```python
from sdk_reforge import ConfigValue, StringList, ProtoContext, ContextSet, ContextShape, LogLevel, Json, Schema

# Create a config value
config_value = ConfigValue(string="example value")

# Create a JSON value
json_value = ConfigValue(json=Json(json='{"key": "value"}'))

# Create a Schema value
schema_value = Schema(definition='{"type": "object", "properties": {"name": {"type": "string"}}}')
```

See full documentation https://docs.reforge.com/docs/sdks/python

## Development

1. Ensure that `poetry` is installed: https://python-poetry.org/docs/#installation
2. From the root of this directory, run `poetry install` to ensure dependencies are installed
3. `poetry run python` to open a Python REPL with access to the project dependencies

### Running tests

To run all tests, including integration tests

```bash
poetry run pytest tests
```

To run only local tests and skip integration tests

```bash
poetry run pytest tests -k "not integration"
```

To run only one specific test file

```bash
poetry run pytest tests/name_of_test_file.py
```

### Examples

There are examples in [examples](examples/)

### Releasing

1. Run pre-commit hooks to check and fix formatting, other rule enforcement.
   `poetry run pre-commit run --show-diff-on-failure --color=always --all-files`
2. On a branch
   1. Update the version in `pyproject.toml`
   2. Update `CHANGELOG.md`
3. Merge the branch
4. `git tag <version> && git push --tags`
5. `poetry publish --build`
   1. To do this you will need an [pypi.org](https://pypi.org) account, and to be added to this project (ask Michael for an invitation)
