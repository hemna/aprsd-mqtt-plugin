# MQTT Raw Plugin Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `MQTTRawPlugin` class that consumes raw APRS-IS strings from the packet queue and publishes them directly to MQTT with minimal latency.

**Architecture:** Extract shared MQTT connection logic into `MQTTPluginBase`, then create two plugin classes: `MQTTPlugin` (existing, refactored) for decoded JSON packets and `MQTTRawPlugin` (new) for raw strings. Both inherit from the base class.

**Tech Stack:** Python 3.11+, paho-mqtt, oslo.config, APRSD threads framework, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `aprsd_mqtt_plugin/conf/main.py` | Modify | Add `raw_topic` config option |
| `aprsd_mqtt_plugin/aprsd_mqtt_plugin.py` | Refactor | Extract `MQTTPluginBase`, keep `MQTTPlugin`, add `MQTTRawPlugin` |
| `aprsd_mqtt_plugin/__init__.py` | Modify | Export both plugin classes |
| `tests/test_mqtt_plugin_base.py` | Create | Unit tests for base class |
| `tests/test_mqtt_plugin.py` | Create | Unit tests for decoded plugin |
| `tests/test_mqtt_raw_plugin.py` | Create | Unit tests for raw plugin |

---

## Chunk 1: Configuration

### Task 1: Add raw_topic config option

**Files:**
- Modify: `aprsd_mqtt_plugin/conf/main.py:35-40`

- [ ] **Step 1: Add raw_topic option to config**

In `aprsd_mqtt_plugin/conf/main.py`, add a new `StrOpt` for `raw_topic` after the existing `topic` option (around line 39):

```python
cfg.StrOpt(
    "raw_topic",
    default="aprsd/raw",
    help="The MQTT Topic to publish raw APRS-IS packets to",
),
```

- [ ] **Step 2: Verify config loads**

Run: `python -c "from aprsd_mqtt_plugin.conf import main; print([o.name for o in main.plugin_opts])"`
Expected: List includes `'raw_topic'`

- [ ] **Step 3: Commit**

```bash
git add aprsd_mqtt_plugin/conf/main.py
git commit -m "feat: add raw_topic config option for raw packet publishing"
```

---

## Chunk 2: MQTTPluginBase

### Task 2: Create MQTTPluginBase class

**Files:**
- Modify: `aprsd_mqtt_plugin/aprsd_mqtt_plugin.py`
- Create: `tests/test_mqtt_plugin_base.py`

- [ ] **Step 1: Write failing test for base class setup**

Create `tests/test_mqtt_plugin_base.py`:

```python
#!/usr/bin/env python
"""Tests for MQTTPluginBase class."""

import pytest
from unittest.mock import MagicMock, patch


class TestMQTTPluginBase:
    """Tests for the MQTTPluginBase class."""

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_setup_mqtt_client_creates_client(self, mock_conf, mock_mqtt_client):
        """Test that setup_mqtt_client creates and connects MQTT client."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase

        # Configure mock
        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = 'localhost'
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.password = None
        mock_conf.callsign = 'TEST'

        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance

        base = MQTTPluginBase()
        result = base.setup_mqtt_client()

        assert result is True
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.loop_start.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mqtt_plugin_base.py::TestMQTTPluginBase::test_setup_mqtt_client_creates_client -v`
Expected: FAIL with `ImportError` or `AttributeError` (MQTTPluginBase doesn't exist yet)

- [ ] **Step 3: Write MQTTPluginBase class**

In `aprsd_mqtt_plugin/aprsd_mqtt_plugin.py`, add the base class before the existing `MQTTPlugin` class. Insert after the imports and before `class MQTTPlugin`:

```python
class MQTTPluginBase:
    """Base class with shared MQTT connection logic.
    
    Provides:
    - setup_mqtt_client(): Create and connect MQTT client
    - on_connect/on_disconnect: Connection callbacks
    - publish(): Publish with queue-full handling
    - stop_mqtt_client(): Cleanup
    """
    
    client = None
    publish_failures = 0
    queue_full_count = 0
    recent_queue_full = 0

    def setup_mqtt_client(self) -> bool:
        """Set up MQTT client connection.
        
        Returns:
            True if setup successful, False otherwise.
        """
        if not CONF.aprsd_mqtt_plugin.enabled:
            LOG.info("MQTT Plugin not enabled in config.")
            return False

        if not CONF.aprsd_mqtt_plugin.host_ip:
            LOG.error("aprsd_mqtt_plugin MQTT host_ip not set.")
            return False

        # Make sure the client id is unique per aprsd instance
        client_id = "aprsd_mqtt_plugin" + CONF.callsign
        LOG.info(f"Using MQTT client id: {client_id}")

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        if CONF.aprsd_mqtt_plugin.user:
            self.client.username_pw_set(
                CONF.aprsd_mqtt_plugin.user,
                CONF.aprsd_mqtt_plugin.password,
            )

        # Set max queued messages to prevent unbounded queue growth
        max_queue = getattr(CONF.aprsd_mqtt_plugin, "max_queued_messages", 1000)
        self.client.max_queued_messages_set(max_queue)
        LOG.info(f"MQTT max_queued_messages set to {max_queue}")

        self.mqtt_properties = Properties(PacketTypes.PUBLISH)
        self.mqtt_properties.MessageExpiryInterval = 30  # in seconds
        
        LOG.info(
            f"Connecting to mqtt://{CONF.aprsd_mqtt_plugin.host_ip}:{CONF.aprsd_mqtt_plugin.host_port}"
        )
        self.client.connect(
            CONF.aprsd_mqtt_plugin.host_ip,
            port=CONF.aprsd_mqtt_plugin.host_port,
            keepalive=60,
        )
        # Start the client's event loop thread
        self.client.loop_start()

        # Track publish failures for monitoring
        self.publish_failures = 0
        self.queue_full_count = 0
        self.recent_queue_full = 0
        
        return True

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        """Callback when MQTT client connects."""
        LOG.info(
            f"Connected to mqtt://{CONF.aprsd_mqtt_plugin.host_ip}:"
            f"{CONF.aprsd_mqtt_plugin.host_port} (reason_code={reason_code})",
        )

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Callback when MQTT client disconnects."""
        LOG.warning(f"MQTT client disconnected (reason_code={reason_code})")

    def publish(self, topic: str, payload: bytes | str) -> bool:
        """Publish payload to MQTT topic with queue-full handling.
        
        Args:
            topic: MQTT topic to publish to
            payload: Message payload (bytes or string)
            
        Returns:
            True if published successfully, False otherwise.
        """
        # Check if client is connected before attempting to publish
        if not self.client or not self.client.is_connected():
            LOG.warning("MQTT client is disconnected, skipping packet.")
            return False

        # If queue has been consistently full recently, skip
        if self.recent_queue_full > 500:
            LOG.warning(
                f"MQTT publish queue has been consistently full for "
                f"{self.recent_queue_full} packets. Skipping packet."
            )
            return False

        try:
            result = self.client.publish(
                topic,
                payload=payload,
                qos=0,
            )

            if result.rc == mqtt.MQTT_ERR_QUEUE_SIZE:
                self.queue_full_count += 1
                self.recent_queue_full += 1
                if self.queue_full_count % 100 == 1:
                    LOG.warning(
                        f"MQTT publish queue is full! Dropping packets. "
                        f"Total queue full events: {self.queue_full_count}."
                    )
                return False
            elif result.rc == mqtt.MQTT_ERR_SUCCESS:
                if self.recent_queue_full > 0:
                    self.recent_queue_full = max(0, self.recent_queue_full - 1)
                return True
            else:
                self.publish_failures += 1
                if self.publish_failures % 100 == 1:
                    LOG.error(
                        f"MQTT publish failed with error code {result.rc}. "
                        f"Total failures: {self.publish_failures}"
                    )
                return False
        except Exception as e:
            self.publish_failures += 1
            if self.publish_failures % 100 == 1:
                LOG.error(
                    f"MQTT publish exception: {e} (total failures: {self.publish_failures})"
                )
            return False

    def stop_mqtt_client(self):
        """Stop the MQTT client loop and disconnect cleanly."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                LOG.info("MQTT client stopped and disconnected")
            except Exception as e:
                LOG.error(f"Error stopping MQTT client: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mqtt_plugin_base.py::TestMQTTPluginBase::test_setup_mqtt_client_creates_client -v`
Expected: PASS

- [ ] **Step 5: Write test for publish method**

Add to `tests/test_mqtt_plugin_base.py`:

```python
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_publish_success(self, mock_conf, mock_mqtt_client):
        """Test that publish sends to MQTT broker."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase
        import paho.mqtt.client as mqtt

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = 'localhost'
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.callsign = 'TEST'

        mock_client_instance = MagicMock()
        mock_client_instance.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client_instance.publish.return_value = mock_publish_result
        mock_mqtt_client.return_value = mock_client_instance

        base = MQTTPluginBase()
        base.setup_mqtt_client()
        
        result = base.publish("test/topic", b"test payload")

        assert result is True
        mock_client_instance.publish.assert_called_once_with(
            "test/topic",
            payload=b"test payload",
            qos=0,
        )

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_publish_skips_when_disconnected(self, mock_conf, mock_mqtt_client):
        """Test that publish skips when client is disconnected."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = 'localhost'
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.callsign = 'TEST'

        mock_client_instance = MagicMock()
        mock_client_instance.is_connected.return_value = False
        mock_mqtt_client.return_value = mock_client_instance

        base = MQTTPluginBase()
        base.setup_mqtt_client()
        
        result = base.publish("test/topic", b"test payload")

        assert result is False
        mock_client_instance.publish.assert_not_called()
```

- [ ] **Step 6: Run all base class tests**

Run: `pytest tests/test_mqtt_plugin_base.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add aprsd_mqtt_plugin/aprsd_mqtt_plugin.py tests/test_mqtt_plugin_base.py
git commit -m "feat: add MQTTPluginBase class with shared MQTT connection logic"
```

---

## Chunk 3: Refactor MQTTPlugin

### Task 3: Refactor MQTTPlugin to use base class

**Files:**
- Modify: `aprsd_mqtt_plugin/aprsd_mqtt_plugin.py`
- Create: `tests/test_mqtt_plugin.py`

- [ ] **Step 1: Write failing test for refactored MQTTPlugin**

Create `tests/test_mqtt_plugin.py`:

```python
#!/usr/bin/env python
"""Tests for MQTTPlugin class."""

import pytest
from unittest.mock import MagicMock, patch


class TestMQTTPlugin:
    """Tests for the refactored MQTTPlugin class."""

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_inherits_from_base(self, mock_conf, mock_mqtt_client):
        """Test that MQTTPlugin inherits from MQTTPluginBase."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPlugin, MQTTPluginBase

        assert issubclass(MQTTPlugin, MQTTPluginBase)

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_filter_publishes_json(self, mock_conf, mock_mqtt_client):
        """Test that filter() publishes packet as JSON to topic."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPlugin
        from aprsd import packets
        import paho.mqtt.client as mqtt

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = 'localhost'
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.topic = 'aprsd/packets'
        mock_conf.callsign = 'TEST'

        mock_client_instance = MagicMock()
        mock_client_instance.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client_instance.publish.return_value = mock_publish_result
        mock_mqtt_client.return_value = mock_client_instance

        plugin = MQTTPlugin()

        # Create a mock packet
        mock_packet = MagicMock()
        mock_packet.raw_dict = {"from": "N0CALL", "to": "APRS"}

        result = plugin.filter(mock_packet)

        # Verify publish was called with the topic
        assert mock_client_instance.publish.called
        call_args = mock_client_instance.publish.call_args
        assert call_args[0][0] == 'aprsd/packets'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mqtt_plugin.py::TestMQTTPlugin::test_inherits_from_base -v`
Expected: FAIL (MQTTPlugin doesn't inherit from MQTTPluginBase yet)

- [ ] **Step 3: Refactor MQTTPlugin to inherit from base**

Replace the existing `MQTTPlugin` class with:

```python
class MQTTPlugin(MQTTPluginBase, plugin.APRSDPluginBase):
    """APRSD plugin that publishes decoded packets as JSON to MQTT.
    
    Inherits MQTT connection logic from MQTTPluginBase.
    Uses the filter hook to receive decoded packets.
    """
    
    enabled = False

    def setup(self):
        """Set up the plugin and MQTT connection."""
        self.enabled = self.setup_mqtt_client()
        if self.enabled:
            # Subscribe to topic on connect (for potential future use)
            self.client.subscribe(CONF.aprsd_mqtt_plugin.topic)

    def stop(self):
        """Stop the plugin and MQTT connection."""
        self.stop_mqtt_client()

    @hookimpl
    def filter(self, packet: packets.core.Packet):
        result = packets.NULL_MESSAGE
        if self.enabled:
            self.rx_inc()
            try:
                result = self.process(packet)
            except Exception as ex:
                LOG.error(
                    "Plugin {} failed to process packet {}".format(
                        self.__class__,
                        ex,
                    ),
                )
            if result:
                self.tx_inc()

        return result

    def process(self, packet: packets.core.Packet):
        """Process packet and publish to MQTT as JSON."""
        if self.tx_count % 200 == 0:
            LOG.debug(
                f"MQTTPlugin Publishing packet ({self.tx_count}) to mqtt://"
                f"{CONF.aprsd_mqtt_plugin.host_ip}:{CONF.aprsd_mqtt_plugin.host_port}"
                f"/{CONF.aprsd_mqtt_plugin.topic}",
            )
            if self.queue_full_count > 0:
                LOG.warning(
                    f"MQTT publish queue full count: {self.queue_full_count}, "
                    f"publish failures: {self.publish_failures}"
                )

        self.publish(
            CONF.aprsd_mqtt_plugin.topic,
            orjson.dumps(packet.raw_dict),
        )

        return packets.NULL_MESSAGE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mqtt_plugin.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add aprsd_mqtt_plugin/aprsd_mqtt_plugin.py tests/test_mqtt_plugin.py
git commit -m "refactor: MQTTPlugin now inherits from MQTTPluginBase"
```

---

## Chunk 4: MQTTRawPlugin

### Task 4: Create MQTTRawPlugin class

**Files:**
- Modify: `aprsd_mqtt_plugin/aprsd_mqtt_plugin.py`
- Create: `tests/test_mqtt_raw_plugin.py`

- [ ] **Step 1: Write failing test for MQTTRawPlugin**

Create `tests/test_mqtt_raw_plugin.py`:

```python
#!/usr/bin/env python
"""Tests for MQTTRawPlugin class."""

import pytest
import queue
from unittest.mock import MagicMock, patch


class TestMQTTRawPlugin:
    """Tests for the MQTTRawPlugin class."""

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_inherits_from_base_and_thread(self, mock_conf, mock_mqtt_client):
        """Test that MQTTRawPlugin inherits from MQTTPluginBase and APRSDFilterThread."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin, MQTTPluginBase
        from aprsd.threads.rx import APRSDFilterThread

        assert issubclass(MQTTRawPlugin, MQTTPluginBase)
        assert issubclass(MQTTRawPlugin, APRSDFilterThread)

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.APRSDFilterThread.__init__')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_constructor_accepts_packet_queue(self, mock_conf, mock_mqtt_client, mock_thread_init):
        """Test that constructor accepts packet_queue parameter."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin

        mock_thread_init.return_value = None
        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = 'localhost'
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.raw_topic = 'aprsd/raw'
        mock_conf.callsign = 'TEST'

        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance

        packet_queue = queue.Queue()
        plugin = MQTTRawPlugin(packet_queue)

        assert plugin.packet_queue is packet_queue

    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.APRSDFilterThread.__init__')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client')
    @patch('aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF')
    def test_loop_publishes_raw_string(self, mock_conf, mock_mqtt_client, mock_thread_init):
        """Test that loop() pulls from queue and publishes raw string."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin
        import paho.mqtt.client as mqtt

        mock_thread_init.return_value = None
        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = 'localhost'
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.raw_topic = 'aprsd/raw'
        mock_conf.callsign = 'TEST'

        mock_client_instance = MagicMock()
        mock_client_instance.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client_instance.publish.return_value = mock_publish_result
        mock_mqtt_client.return_value = mock_client_instance

        packet_queue = queue.Queue()
        raw_packet = "N0CALL>APRS,WIDE1-1:>status text"
        packet_queue.put(raw_packet)

        plugin = MQTTRawPlugin(packet_queue)
        plugin.loop()

        # Verify publish was called with raw string
        mock_client_instance.publish.assert_called_once()
        call_args = mock_client_instance.publish.call_args
        assert call_args[0][0] == 'aprsd/raw'
        assert call_args[1]['payload'] == raw_packet
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mqtt_raw_plugin.py::TestMQTTRawPlugin::test_inherits_from_base_and_thread -v`
Expected: FAIL (MQTTRawPlugin doesn't exist yet)

- [ ] **Step 3: Add APRSDFilterThread import**

At the top of `aprsd_mqtt_plugin/aprsd_mqtt_plugin.py`, add to the imports:

```python
from aprsd.threads.rx import APRSDFilterThread
import queue
```

- [ ] **Step 4: Write MQTTRawPlugin class**

Add after the `MQTTPlugin` class:

```python
class MQTTRawPlugin(MQTTPluginBase, APRSDFilterThread):
    """APRSD plugin that publishes raw APRS-IS strings to MQTT.
    
    Consumes raw packets directly from the packet queue before decoding.
    Maximum throughput - subscriber handles all parsing.
    
    Inherits:
        MQTTPluginBase: MQTT connection logic
        APRSDFilterThread: APRSD threading pattern
    """

    def __init__(self, packet_queue: queue.Queue):
        """Initialize the raw packet plugin.
        
        Args:
            packet_queue: Queue to consume raw packets from
        """
        APRSDFilterThread.__init__(self, 'MQTTRawPlugin', packet_queue)
        self.packet_queue = packet_queue
        self.enabled = self.setup_mqtt_client()
        
        if not CONF.aprsd_mqtt_plugin.raw_topic:
            LOG.error("aprsd_mqtt_plugin raw_topic not set. Disabling plugin.")
            self.enabled = False

    def loop(self) -> bool:
        """Pull raw packet from queue and publish to MQTT.
        
        Returns:
            True to keep thread running, False to stop.
        """
        if not self.enabled:
            return True
            
        try:
            raw_packet = self.packet_queue.get(timeout=1)
            self.packet_count += 1
            
            if self.packet_count % 200 == 0:
                LOG.debug(
                    f"MQTTRawPlugin Publishing packet ({self.packet_count}) to mqtt://"
                    f"{CONF.aprsd_mqtt_plugin.host_ip}:{CONF.aprsd_mqtt_plugin.host_port}"
                    f"/{CONF.aprsd_mqtt_plugin.raw_topic}",
                )
                if self.queue_full_count > 0:
                    LOG.warning(
                        f"MQTT publish queue full count: {self.queue_full_count}, "
                        f"publish failures: {self.publish_failures}"
                    )

            # Publish raw string directly - no decoding, no JSON
            self.publish(
                CONF.aprsd_mqtt_plugin.raw_topic,
                raw_packet,
            )
        except queue.Empty:
            pass
            
        return True

    def stop(self):
        """Stop the plugin thread and MQTT connection."""
        self.stop_mqtt_client()
        super().stop()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_mqtt_raw_plugin.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add aprsd_mqtt_plugin/aprsd_mqtt_plugin.py tests/test_mqtt_raw_plugin.py
git commit -m "feat: add MQTTRawPlugin for raw APRS-IS packet publishing"
```

---

## Chunk 5: Exports and Final Integration

### Task 5: Update package exports

**Files:**
- Modify: `aprsd_mqtt_plugin/__init__.py`

- [ ] **Step 1: Write test for package exports**

Add to `tests/test_mqtt_plugin.py`:

```python
def test_package_exports_both_plugins():
    """Test that package exports both plugin classes."""
    from aprsd_mqtt_plugin import MQTTPlugin, MQTTRawPlugin
    
    assert MQTTPlugin is not None
    assert MQTTRawPlugin is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mqtt_plugin.py::test_package_exports_both_plugins -v`
Expected: FAIL (imports not available from package)

- [ ] **Step 3: Update __init__.py to export both classes**

Replace the contents of `aprsd_mqtt_plugin/__init__.py` with:

```python
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import pbr.version

from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPlugin, MQTTRawPlugin


__version__ = pbr.version.VersionInfo("aprsd_mqtt_plugin").version_string()
__all__ = ["MQTTPlugin", "MQTTRawPlugin", "__version__"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mqtt_plugin.py::test_package_exports_both_plugins -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add aprsd_mqtt_plugin/__init__.py tests/test_mqtt_plugin.py
git commit -m "feat: export both MQTTPlugin and MQTTRawPlugin from package"
```

---

## Chunk 6: Documentation

### Task 6: Update README

**Files:**
- Modify: `README.rst`

- [ ] **Step 1: Add MQTTRawPlugin documentation**

Add a new section to `README.rst` after the existing usage section explaining `MQTTRawPlugin`:

```rst
Raw Packet Mode
---------------

For maximum throughput, use ``MQTTRawPlugin`` instead of ``MQTTPlugin``.
This publishes raw APRS-IS strings directly to MQTT without decoding.

Configure in your APRSD config:

.. code-block:: yaml

    [aprsd_mqtt_plugin]
    enabled = True
    host_ip = localhost
    host_port = 1883
    raw_topic = aprsd/raw

Enable the raw plugin:

.. code-block:: yaml

    enabled_plugins = aprsd_mqtt_plugin.aprsd_mqtt_plugin.MQTTRawPlugin

Raw packets are published as plain strings, e.g.::

    N0CALL>APRS,WIDE1-1:>status text

The MQTT subscriber is responsible for parsing the raw APRS packets.
```

- [ ] **Step 2: Commit**

```bash
git add README.rst
git commit -m "docs: add MQTTRawPlugin usage documentation"
```

---

## Chunk 7: Final Verification

### Task 7: Full test run and cleanup

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run linter**

Run: `tox -e lint` or `ruff check aprsd_mqtt_plugin/`
Expected: No errors

- [ ] **Step 3: Run formatter**

Run: `tox -e fmt` or `ruff format aprsd_mqtt_plugin/`
Expected: Files formatted

- [ ] **Step 4: Final commit if any formatting changes**

```bash
git add -A
git commit -m "style: apply formatting"
```

- [ ] **Step 5: Verify installation works**

Run: `pip install -e . && python -c "from aprsd_mqtt_plugin import MQTTPlugin, MQTTRawPlugin; print('OK')"`
Expected: Prints "OK"
