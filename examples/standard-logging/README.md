## Standard Logging Example

This example demonstrates how to use Reforge's `LoggerFilter` to dynamically control log levels for standard Python logging.

### Features

- Dynamic log level control through Reforge configuration
- No application restart required to change log levels
- Works with standard Python `logging` module
- Can target specific loggers by name using context-based rules

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
poetry run python standard_logging_example.py
```

The example will log messages at all levels (DEBUG, INFO, WARNING, ERROR) every second.

### Dynamic Control

While the example is running, you can:

1. Change the log level in your Reforge dashboard
2. See the output change in real-time without restarting the application
3. Use context-based rules to set different levels for different loggers

For example, you could create rules like:

- Set `DEBUG` level for `reforge.python.*` loggers
- Set `ERROR` level for all other loggers
- Set `INFO` level during business hours, `DEBUG` level at night

### How It Works

The `LoggerFilter` integrates with Python's standard logging by:

1. Implementing the `logging.Filter` interface
2. Querying Reforge config for the log level on each log message
3. Returning `True` (allow) or `False` (block) based on the configured level
4. Using a context containing the logger name for targeted rules

### Advanced Usage

You can customize the logger name lookup by subclassing `LoggerFilter`:

```python
class CustomLoggerFilter(LoggerFilter):
    def logger_name(self, record: logging.LogRecord) -> str:
        # Custom logic to derive logger name
        return record.name.replace("myapp", "mycompany")
```
