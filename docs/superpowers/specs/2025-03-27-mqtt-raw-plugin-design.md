# MQTT Raw Plugin Design

## Summary

Add a new `MQTTRawPlugin` class that consumes raw APRS-IS strings from the packet queue and publishes them directly to MQTT. This enables subscribers to receive packets with minimal latency and handle parsing themselves.

## Problem

The existing `MQTTPlugin` receives decoded/parsed packets through APRSD's filter hook chain. This adds latency from:
- Packet decoding
- Duplicate filtering
- Plugin hook processing

For use cases where the MQTT subscriber wants to handle raw packets as quickly as possible, we need a path that bypasses this processing.

## Solution

Refactor the existing code to extract shared MQTT connection logic into a base class, then create two plugin classes:

1. **MQTTPlugin** - Existing behavior, publishes decoded JSON packets
2. **MQTTRawPlugin** - New, publishes raw APRS-IS strings

Users select which plugin to use in their APRSD configuration. Only one runs at a time.

## Class Architecture

```
MQTTPluginBase
├── MQTT client setup (paho-mqtt)
├── Connection callbacks (on_connect, on_disconnect)
├── Publish method with queue-full handling
├── Stop/cleanup lifecycle
└── Shared config (host, port, user, password, max_queued_messages)

MQTTPlugin(MQTTPluginBase, APRSDPluginBase)
├── Inherits MQTT logic from base
├── Uses @hookimpl filter() for decoded packets
├── Publishes JSON (orjson) to configured topic
└── Existing behavior preserved

MQTTRawPlugin(MQTTPluginBase, APRSDFilterThread)
├── Inherits MQTT logic from base
├── Inherits thread pattern from APRSDFilterThread
├── Constructor receives packet_queue
├── loop() pulls raw strings, publishes to raw_topic
└── No decoding, no filtering - maximum throughput
```

## Configuration

All options in `[aprsd_mqtt_plugin]` section:

```ini
[aprsd_mqtt_plugin]
# Shared options (used by both plugins)
enabled = True
host_ip = localhost
host_port = 1883
user = 
password = 
max_queued_messages = 1000

# Topic options (each plugin uses its relevant one)
topic = aprsd/packets       # Used by MQTTPlugin (decoded JSON)
raw_topic = aprsd/raw       # Used by MQTTRawPlugin (raw strings)
```

Plugin selection happens in APRSD's main config:

```ini
# User picks ONE:
enabled_plugins = aprsd_mqtt_plugin.aprsd_mqtt_plugin.MQTTPlugin
# OR
enabled_plugins = aprsd_mqtt_plugin.aprsd_mqtt_plugin.MQTTRawPlugin
```

### New Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `raw_topic` | string | `aprsd/raw` | MQTT topic for raw APRS-IS strings |

## Data Flow

### MQTTPlugin (decoded mode) - unchanged

```
APRS-IS → APRSDRXThread → packet_queue → APRSDFilterThread (decode/filter)
    → plugin.filter() hook → MQTTPlugin.filter() → JSON to MQTT topic
```

### MQTTRawPlugin (raw mode)

```
APRS-IS → APRSDRXThread → packet_queue → MQTTRawPlugin.loop()
    → raw string directly to MQTT raw_topic
```

Key differences:
- `MQTTRawPlugin` pulls raw strings from `packet_queue` directly in its `loop()` method
- No decoding, no filtering, no plugin hook chain
- Raw APRS-IS string published as-is (e.g., `N0CALL>APRS,WIDE1-1:>status text`)
- Maximum throughput - subscriber handles all parsing

## File Structure

```
aprsd_mqtt_plugin/
├── __init__.py              # Export both plugin classes
├── aprsd_mqtt_plugin.py     # Refactored:
│   ├── MQTTPluginBase       # New - shared MQTT logic
│   ├── MQTTPlugin           # Refactored - inherits from base
│   └── MQTTRawPlugin        # New - raw packet consumer
├── conf/
│   └── opts.py              # Add raw_topic config option
└── cli.py                   # Unchanged
```

## Implementation Details

### MQTTPluginBase

Contains shared MQTT logic extracted from existing `MQTTPlugin`:

- `setup_mqtt_client()` - client creation, callbacks, connection
- `on_connect()`, `on_disconnect()` - connection callbacks  
- `publish(topic, payload)` - publish with queue-full handling, failure tracking
- `stop_mqtt_client()` - cleanup

### MQTTPlugin Changes

- Inherits `MQTTPluginBase` + `APRSDPluginBase`
- `setup()` calls `self.setup_mqtt_client()`
- `stop()` calls `self.stop_mqtt_client()`
- `filter()` and `process()` unchanged, use `self.publish(topic, payload)`

### MQTTRawPlugin

- Inherits `MQTTPluginBase` + `APRSDFilterThread`
- Constructor takes `packet_queue`
- `setup()` calls `self.setup_mqtt_client()`
- `loop()` pulls from queue, calls `self.publish(raw_topic, raw_string)`
- No decoding, no JSON serialization

## Error Handling

### Queue-full handling (shared in base)

- Existing logic preserved: track `queue_full_count`, `recent_queue_full`, `publish_failures`
- Skip publishing when queue consistently full (>500 recent failures)
- Log warnings at intervals to avoid spam

### Connection handling (shared in base)

- `on_disconnect` logs warning, paho-mqtt handles reconnection automatically
- Skip publishing when disconnected (check `client.is_connected()`)

### MQTTRawPlugin specific

- `loop()` uses `packet_queue.get(timeout=1)` - blocks with timeout, returns `True` to keep thread alive on `queue.Empty`
- No packet validation - raw strings published as-is, subscriber handles malformed data
- Thread stops cleanly via `APRSDThread.stop()` mechanism

### Startup validation

- Both plugins check `enabled` and `host_ip` in setup
- `MQTTRawPlugin` validates `raw_topic` is configured
- `MQTTPlugin` validates `topic` is configured

## Testing

### Unit tests

- `MQTTPluginBase`: mock paho-mqtt client, verify connection setup, publish behavior, queue-full handling
- `MQTTPlugin`: verify it calls base methods, filter hook works, JSON serialization
- `MQTTRawPlugin`: verify loop pulls from queue, publishes raw strings, no transformation

### Integration tests

- Spin up local MQTT broker (mosquitto in test container or mock)
- `MQTTRawPlugin`: push raw strings to queue, verify they arrive on `raw_topic` unchanged
- `MQTTPlugin`: push decoded packets, verify JSON arrives on `topic`

### Test files

```
tests/
├── test_mqtt_plugin_base.py   # Base class tests
├── test_mqtt_plugin.py        # Decoded plugin tests  
└── test_mqtt_raw_plugin.py    # Raw plugin tests
```

## Backward Compatibility

- Existing `MQTTPlugin` behavior unchanged
- Default config values preserve current behavior
- Users must explicitly choose `MQTTRawPlugin` to get new functionality
