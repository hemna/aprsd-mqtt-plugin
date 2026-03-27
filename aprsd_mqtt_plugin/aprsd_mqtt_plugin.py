import abc
import logging
import queue

import orjson
import paho.mqtt.client as mqtt
import pluggy
from aprsd import packets, plugin
from aprsd.threads.rx import APRSDFilterThread
from oslo_config import cfg
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from aprsd_mqtt_plugin import conf  # noqa


CONF = cfg.CONF
LOG = logging.getLogger("APRSD")
hookimpl = pluggy.HookimplMarker("aprsd")


class MQTTPluginBase(metaclass=abc.ABCMeta):
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

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ):
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


class MQTTPlugin(plugin.APRSDPluginBase, MQTTPluginBase):
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


class MQTTRawPlugin(APRSDFilterThread, MQTTPluginBase):
    """APRSD plugin that publishes raw APRS-IS strings to MQTT.

    Consumes raw packets directly from the packet queue before decoding.
    Maximum throughput - subscriber handles all parsing.

    Inherits:
        APRSDFilterThread: APRSD threading pattern
        MQTTPluginBase: MQTT connection logic
    """

    def __init__(self, packet_queue: queue.Queue):
        """Initialize the raw packet plugin.

        Args:
            packet_queue: Queue to consume raw packets from
        """
        APRSDFilterThread.__init__(self, "MQTTRawPlugin", packet_queue)
        self.packet_queue = packet_queue
        self.packet_count = 0
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
