## Structlog Example

This example demonstrates how to use Reforge's `LoggerProcessor` to dynamically control log levels for structlog.

### Features

- Dynamic log level control through Reforge configuration
- No application restart required to change log levels
- Works with structlog's processor pipeline
- Can target specific loggers by name using context-based rules
- Integrates seamlessly with structlog's structured logging features

### Setup

1. Install dependencies:

   ```bash
   poetry install --no-root
   ```

2. Set your Reforge SDK key (or use local-only mode as in the example):

   ```bash
   export REFORGE_SDK_KEY=your-sdk-key-here
   ```

3. Create a log level config in your Reforge dashboard:
   - Config key: `log-levels.default`
   - Type: `LOG_LEVEL_V2`
   - Default value: `INFO` (or your preferred level)

### Running the Example

```bash
poetry run python structlog_example.py
```

The example will log messages at all levels (DEBUG, INFO, WARNING, ERROR) every second.

### Dynamic Control

While the example is running, you can:

1. Change the log level in your Reforge dashboard
2. See the output change in real-time without restarting the application
3. Use context-based rules to set different levels for different modules

For example, you could create rules like:

- Set `DEBUG` level for `myapp.database` module
- Set `ERROR` level for all other modules
- Set `INFO` level during business hours, `DEBUG` level at night

### How It Works

The `LoggerProcessor` integrates with structlog by:

1. Implementing a processor in the structlog pipeline
2. Querying Reforge config for the log level on each log event
3. Raising `DropEvent` to filter messages below the configured level
4. Using a context containing the logger name for targeted rules

**Important**: The `LoggerProcessor` must come **after** `structlog.stdlib.add_log_level` in the processor pipeline, as it depends on the level information added by that processor.

### Advanced Usage

You can customize the logger name lookup by subclassing `LoggerProcessor`:

```python
class CustomLoggerNameProcessor(LoggerProcessor):
    def logger_name(self, logger, event_dict: dict) -> str:
        # Use module name as logger name
        return event_dict.get("module", "unknown")
```

This allows you to create log level rules based on module names, file names, or any other field in the event dictionary.

### Structlog Installation

Structlog is an optional dependency. To install the SDK with structlog support:

```bash
pip install sdk-reforge[structlog]
```

Or in your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
sdk-reforge = {version = "^1.0", extras = ["structlog"]}
```
