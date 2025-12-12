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

## Features

The APRSD MQTT Plugin publishes APRS packets to an MQTT broker, allowing you to integrate APRSD with MQTT-based systems. Key features include:

-   **MQTT Publishing**: Automatically publishes all received APRS packets to a configured MQTT topic
-   **JSON Format**: Packets are published as JSON for easy consumption by other systems
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

### MQTT Plugin Configuration

Add the following section to your APRSD configuration file to configure the MQTT plugin:

``` yaml
[aprsd_mqtt_plugin]
# Enable the MQTT plugin (default: False)
enabled = True

# MQTT broker hostname or IP address (required)
host_ip = localhost

# MQTT broker port (default: 1883)
host_port = 1883

# MQTT topic to publish packets to (default: aprsd/packets)
topic = aprsd/packets

# Optional: MQTT username for authentication
user =

# Optional: MQTT password for authentication
password =
```

### Example Configuration

Here's a complete example configuration:

``` yaml
[aprsd_mqtt_plugin]
enabled = True
host_ip = mqtt.example.com
host_port = 1883
topic = aprsd/packets
user = mqtt_user
password = mqtt_password
```

### Enable the Plugin

To enable the plugin, add it to the `enabled_plugins` section of your APRSD configuration:

``` ini
[aprsd]
enabled_plugins = aprsd_mqtt_plugin.aprsd_mqtt_plugin.MQTTPlugin
```

## Usage

Once installed and configured, the MQTT plugin will automatically start when you run `aprsd server`.

### How It Works

The plugin:

1.  Connects to the configured MQTT broker on startup
2.  Subscribes to the configured topic
3.  Publishes all received APRS packets as JSON to the MQTT topic
4.  Maintains a persistent connection to the broker

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

Note: Additional fields may be present in the JSON payload.

### Verifying It's Working

After starting APRSD, check the logs for messages like:

```
INFO: Connecting to mqtt://localhost:1883
INFO: Connected to mqtt://localhost:1883/aprsd/packets (0)
```

You can also subscribe to the MQTT topic using an MQTT client:

``` console
$ mosquitto_sub -h localhost -t aprsd/packets
```

Or using `mqtt-cli`:

``` console
$ mqtt sub -t aprsd/packets
```

### Integration Examples

**Home Assistant Integration:**

``` yaml
mqtt:
  sensor:
    - name: "APRS Packet"
      state_topic: "aprsd/packets"
      value_template: "{{ value_json.message_text }}"
```

**Node-RED Integration:**

Connect an MQTT input node to `aprsd/packets` and parse the JSON payload.

**Custom Application:**

Subscribe to the MQTT topic and process the JSON packets in your application.

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
