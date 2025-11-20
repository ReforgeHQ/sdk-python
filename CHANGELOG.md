# Changelog

## [1.1.1] - 2025-11-20

- Fix InternalLogger to properly register with Python's logging hierarchy, enabling handler propagation from `logging.basicConfig()` and parent loggers [#18]

## [0.12.0] - 2025-04-14

- Add special case handling for context `prefab.current-time` to return the current time (UTC) to round out new operator support [#124]

## [0.11.4] - 2025-03-14

- Make ConfigValue work as a value in the Context Dictionary. Declare a new type `ContextDictOrContext` to better cover the type possibilities of the context argument [#122]

## [0.11.3] - 2025-03-13

- Re-exported Protocol Buffer types including `ConfigValue`, `StringList`, `ProtoContext`, `ContextSet`, `ContextShape`, `LogLevel`, `Json`, and `Schema` for easier access. [#120]

## [0.11.2] - 2025-02-24

- Updates ConfigValueType's union to include dict to better support json values [#117]
- Renamed encrypted content paths

## [0.11.1] - 2025-02-20

- adds http conditional fetch logic to configuration polling to lower bandwidth requirements [#116]

## [0.11.0] - 2025-02-07

- removes reference to protobuf internal class [#113]
- adds semver, regex, number comparison operator support [#112]
- adds more string operator support [#111]

## [0.10.10] - 2024-09-18

- add separate configuration for the streaming (SSE) config subsystem [#108]
- trim whitespace from api key [#107]

## [0.10.9] - 2024-09-12

- Support json config type [#105]
- better sse connection handling, adds backoffs [#104]

## [0.10.8] - 2024-09-03

- Allow re-setting the global context [#102]
- Change config loading -- now load from belt/suspenders API pair for increased reliability. Load full config once then SSE rather than polling all the time [#98]
- Fail fast on invalid credentials (401 response) [#97]
- Locking fixes in reset_instance command [#95]

## [0.10.7] - 2024-06-07

- Enlarge acceptable version range for mmh3 dependency; add matrix tests to cover v3 and v4 [#93]

## [0.10.6] - 2024-06-07

- Configure timer threads as daemon [#90]

## [0.10.5] - 2024-06-03

- Return stringlist contents as a python list [#85]
- idna update per dependabot [#86]

## [0.10.4] - 2024-04-08

- adds duration support [#82]

## [0.10.3] - 2024-03-19

- Make additional classes visible [#80]

## [0.10.2] - 2024-03-15

- Split structlogger-supporting LogProcessor out, make logger_name derivation overridable [#72]
- Revise logging in telemetry thread to print backtrace [#71]
- Restore logging.Filter superclass on LoggerFilter [#74]
- fix row-index handling when there's only a no-env-id (default) row [#75]
- fix for integration test comparing outgoing telemetry data [#78]

## [0.10.1] - 2024-02-16

- Adds log level name to number conversion for structlog [#69]

## [0.10.0] - 2024-02-13

- Adds full telemetry support - will (configurably) send data back to Prefab about evaluations, logging counts, and context usage
- Reliability changes, increased test coverage
- Remove automatic `structlog` configuration. Adds helper methods to use Prefab in customer-configured structlog [#40]
- Filter extracted for standard `logging` usage [#32]
- Added types on client [#28]
- Changed default collect_sync_interval from None to 30 seconds [#54]
- Added package methods to configure, manage and reset a singleton instance of the client [#53]
- logging overhaul - remove logging via client in favor of a logging filter [#55], [#60]
- Removed GRPC [#56]
- Fix issue where client crashed in absence of HOME env var [#61]
- Added global_context option [#63]
- Removed namespace, other disused options [#64]
- added on_ready_callback [#65]

## [0.9.0] - 2024-01-13

- Add support for reading config from a local JSON datafile [#42]
- Add support for setting and using default contexts [#43]
- Add support for encrypted config values [#44]

## [0.8.0] - 2024-01-12

- Add support for `provided` config values via ENV vars
- Add `ConfigValueWrapper`

## [0.7.0] - 2023-12-22

- Set and load from local cache when specified

## [0.6.0] - 2023-11-14

- Loosen version requirements to allow Python 3.9

## [0.5.1] - 2023-06-28

- Migrate from a direct dependency on `urllib3` to using `requests`

## [0.5.0] - 2023-06-24

- Add ContextShape and ContextShapeAggregator
- Rename LogPathCollector to LogPathAggregator

## [0.4.0] - 2023-06-24

- Better handling for non-valid yaml in YamlParser
- Switch to using https://buf.build/ for generating protos

## [0.3.3] - 2023-06-21

- Move `pytest` and `timecop` to dev dependencies
- Remove outdated call to `base_client.logger()`

## [0.3.2] - 2023-06-20

- Allow using latest urllib 1.x version to avoid forcing users to upgrade to urllib 2+

## [0.3.1] - 2023-06-12

- Ensure `LoggerClient.config_client` is not set until the config client has initialized successfully
- Log collection no longer ignores logs that would not be printed
- Fix bug in read/write locks in ConfigClient during initialization

## [0.3.0] - 2023-06-12

- First published release, includes:
  - Config
  - Feature flags
  - Logging
    - Log metrics
