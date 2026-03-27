# APRSD MQTT Plugin

[![PyPI](https://img.shields.io/pypi/v/aprsd-mqtt-plugin.svg)](https://pypi.org/project/aprsd-mqtt-plugin/)
[![Status](https://img.shields.io/pypi/status/aprsd-mqtt-plugin.svg)](https://pypi.org/project/aprsd-mqtt-plugin/)
[![Python Version](https://img.shields.io/pypi/pyversions/aprsd-mqtt-plugin)](https://pypi.org/project/aprsd-mqtt-plugin)
[![License](https://img.shields.io/pypi/l/aprsd-mqtt-plugin)](https://opensource.org/licenses/Apache%20Software%20License%202.0)

[![Read the Docs](https://img.shields.io/readthedocs/aprsd-mqtt-plugin/latest.svg?label=Read%20the%20Docs)](https://aprsd-mqtt-plugin.readthedocs.io/)
[![Tests](https://github.com/hemna/aprsd-mqtt-plugin/workflows/Tests/badge.svg)](https://github.com/hemna/aprsd-mqtt-plugin/actions?workflow=Tests)
[![Codecov](https://codecov.io/gh/hemna/aprsd-mqtt-plugin/branch/main/graph/badge.svg)](https://codecov.io/gh/hemna/aprsd-mqtt-plugin)

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

---

> [!WARNING]
> Legal operation of this software requires an amateur radio license and a valid call sign.

> [!NOTE]
> Star this repo to follow our progress! This code is under active development, and contributions are both welcomed and appreciated. See [CONTRIBUTING.md](https://github.com/hemna/aprsd-mqtt-plugin/blob/master/CONTRIBUTING.md) for details.

## Plugins Included

This package provides two APRSD plugins for publishing APRS packets to MQTT:

| Plugin | Description | Output Format | Use Case |
|--------|-------------|---------------|----------|
| **MQTTPlugin** | Publishes decoded APRS packets | JSON | Easy integration with home automation, dashboards, databases |
| **MQTTRawPlugin** | Publishes raw APRS-IS strings | Plain text | Maximum throughput, custom parsing, low latency |

Both plugins share the same MQTT connection configuration. Choose the one that best fits your use case - they are **mutually exclusive** (use one or the other, not both).

## Features

-   **Two Operating Modes**: Choose between decoded JSON or raw APRS-IS string publishing
-   **MQTT Publishing**: Automatically publishes all received APRS packets to a configured MQTT topic
-   **JSON Format**: Decoded plugin publishes packets as JSON for easy consumption by other systems
-   **High Performance**: Uses `orjson` for fast JSON serialization (3-10x faster than standard library)
-   **Raw Mode**: Maximum throughput with zero parsing overhead - subscriber handles all decoding
-   **Configurable Broker**: Connect to any MQTT broker (local or remote)
-   **Authentication Support**: Optional username/password authentication for MQTT broker
-   **Real-time Integration**: Enables real-time APRS data streaming to MQTT subscribers

## Requirements

-   `aprsd >= 3.0.0`
-   A running APRSD instance
-   Access to an MQTT broker (Mosquitto, HiveMQ, EMQX, etc.)

## Installation

You can install *APRSD MQTT Plugin* via [pip](https://pip.pypa.io/) from [PyPI](https://pypi.org/):

``` console
$ pip install aprsd-mqtt-plugin
```

Or using `uv`:

``` console
$ uv pip install aprsd-mqtt-plugin
```

## Configuration

Before using the MQTT plugin, you need to configure it in your APRSD configuration file.
Generate a sample configuration file if you haven't already:

``` console
$ aprsd sample-config
```

This will create a configuration file at `~/.config/aprsd/aprsd.conf` (or `aprsd.yml`).

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `False` | Enable the MQTT plugin |
| `host_ip` | (required) | MQTT broker hostname or IP address |
| `host_port` | `1883` | MQTT broker port |
| `user` | (optional) | MQTT username for authentication |
| `password` | (optional) | MQTT password for authentication |
| `topic` | `aprsd/packet` | Topic for decoded JSON packets (MQTTPlugin) |
| `raw_topic` | `aprsd/raw` | Topic for raw APRS-IS strings (MQTTRawPlugin) |

### Complete Configuration Example

``` yaml
[aprsd_mqtt_plugin]
# Enable the MQTT plugin (default: False)
enabled = True

# MQTT broker hostname or IP address (required)
host_ip = mqtt.example.com

# MQTT broker port (default: 1883)
host_port = 1883

# MQTT topic for decoded JSON packets (default: aprsd/packet)
topic = aprsd/packets

# MQTT topic for raw APRS-IS strings (default: aprsd/raw)
raw_topic = aprsd/raw

# Optional: MQTT username for authentication
user = mqtt_user

# Optional: MQTT password for authentication
password = mqtt_password
```

---

## MQTTPlugin (Decoded JSON Mode)

The `MQTTPlugin` receives decoded APRS packets from APRSD, serializes them to JSON using `orjson`, and publishes them to the configured `topic`.

### Enable MQTTPlugin

Add to your APRSD configuration:

``` ini
[aprsd]
enabled_plugins = aprsd_mqtt_plugin.MQTTPlugin
```

### How It Works

1. APRSD receives and decodes APRS packets from APRS-IS
2. MQTTPlugin receives the decoded packet objects via APRSD's plugin hook
3. Packets are serialized to JSON and published to the `topic`
4. Maintains a persistent connection to the MQTT broker

### Packet Format

Packets are published as JSON with the following structure:

``` json
{
  "from": "CALLSIGN",
  "to": "DESTINATION",
  "message_text": "Message content",
  "path": ["WIDE1-1", "WIDE2-2"],
  "timestamp": "2024-01-01T12:00:00"
}
```

Note: Additional fields may be present depending on packet type (position, weather, telemetry, etc.).

### Subscribing to Decoded Packets

``` console
$ mosquitto_sub -h localhost -t aprsd/packets
```

---

## MQTTRawPlugin (Raw APRS-IS Mode)

The `MQTTRawPlugin` consumes raw APRS-IS strings directly from APRSD's packet queue and publishes them without any decoding or transformation. This provides maximum throughput for applications that need to handle parsing themselves.

### Enable MQTTRawPlugin

Add to your APRSD configuration:

``` ini
[aprsd]
enabled_plugins = aprsd_mqtt_plugin.MQTTRawPlugin
```

### How It Works

1. APRSD receives raw APRS-IS strings from the network
2. MQTTRawPlugin pulls raw strings directly from the packet queue (before decoding)
3. Raw strings are published as-is to the `raw_topic`
4. Subscriber is responsible for parsing the APRS protocol

### Packet Format

Raw packets are published as plain text strings exactly as received from APRS-IS:

```
N0CALL>APRS,TCPIP*,qAC,T2TEXAS:>Hello World
WB4BOR-9>APTT4,WIDE1-1,WIDE2-1,qAR,W4KEL-1:!3400.00N/08400.00W>000/000
```

### When to Use Raw Mode

- **Maximum throughput** - No CPU cycles spent on decoding
- **Custom parsing** - You need to parse packets differently than APRSD does
- **Minimal latency** - Fastest path from APRS-IS to your application
- **Data archival** - Store original APRS-IS format for later processing

### Subscribing to Raw Packets

``` console
$ mosquitto_sub -h localhost -t aprsd/raw
```

---

## Verifying It's Working

After starting APRSD, check the logs for messages like:

```
INFO: Connecting to mqtt://localhost:1883
INFO: Connected to mqtt://localhost:1883/aprsd/packets (0)
```

For MQTTRawPlugin:
```
INFO: MQTTRawPlugin Publishing packet (200) to mqtt://localhost:1883/aprsd/raw
```

## Integration Examples

### Home Assistant (Decoded Mode)

``` yaml
mqtt:
  sensor:
    - name: "APRS Packet"
      state_topic: "aprsd/packets"
      value_template: "{{ value_json.message_text }}"
```

### Node-RED

**Decoded mode**: Connect an MQTT input node to `aprsd/packets` and parse the JSON payload.

**Raw mode**: Connect an MQTT input node to `aprsd/raw` and use a function node to parse the raw APRS string.

### Custom Application

Subscribe to either topic and process packets in your application:

```python
import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, msg):
    if msg.topic == "aprsd/packets":
        packet = json.loads(msg.payload)
        print(f"From: {packet['from']}, Message: {packet.get('message_text', '')}")
    elif msg.topic == "aprsd/raw":
        raw = msg.payload.decode()
        print(f"Raw: {raw}")

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("aprsd/#")
client.loop_forever()
```

For more details, see the [Command-line Reference](https://aprsd-mqtt-plugin.readthedocs.io/en/latest/usage.html).

## Contributing

Contributions are very welcome. To learn more, see the [Contributor Guide](CONTRIBUTING.rst).

## License

Distributed under the terms of the [Apache Software License 2.0 license](https://opensource.org/licenses/Apache%20Software%20License%202.0),
*APRSD MQTT Plugin* is free and open source software.

## Issues

If you encounter any problems,
please [file an issue](https://github.com/hemna/aprsd-mqtt-plugin/issues) along with a detailed description.

## Credits

This project was generated from [@hemna](https://github.com/hemna)'s [APRSD Plugin Python Cookiecutter](https://github.com/hemna/cookiecutter-aprsd-plugin) template.
