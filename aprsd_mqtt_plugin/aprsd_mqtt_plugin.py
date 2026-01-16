import logging
import json

import paho.mqtt.client as mqtt
import pluggy
from aprsd import packets, plugin
from oslo_config import cfg
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from aprsd_mqtt_plugin import conf  # noqa


CONF = cfg.CONF
LOG = logging.getLogger("APRSD")
hookimpl = pluggy.HookimplMarker("aprsd")


class MQTTPlugin(plugin.APRSDPluginBase):
    enabled = False
    client = None

    def setup(self):
        """Allows the plugin to do some 'setup' type checks in here.

        If the setup checks fail, set the self.enabled = False.  This
        will prevent the plugin from being called when packets are
        received."""
        # Do some checks here?
        self.enabled = True
        if not CONF.aprsd_mqtt_plugin.enabled:
            LOG.info("Plugin not enabled in config.")
            self.enabled = False
            return

        if not CONF.aprsd_mqtt_plugin.host_ip:
            LOG.error("aprsd_mqtt_plugin MQTT host_ip not set. Disabling plugin")
            self.enabled = False
            return

        # make sure the client id is unique per aprsd instance
        client_id = "aprsd_mqtt_plugin" + CONF.callsign
        LOG.info(f"Using MQTT client id: {client_id}")

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            # transport='websockets',
            # protocol=mqtt.MQTTv5
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        if CONF.aprsd_mqtt_plugin.user:
            self.client.username_pw_set(
                CONF.aprsd_mqtt_plugin.user,
                CONF.aprsd_mqtt_plugin.password,
            )

        # Set max queued messages to prevent unbounded queue growth
        # This prevents memory buildup and blocking when broker is slow
        # Default is 0 (unlimited), setting to 1000 allows some buffering
        # but prevents unbounded growth
        max_queue = getattr(CONF.aprsd_mqtt_plugin, "max_queued_messages", 1000)
        self.client.max_queued_messages_set(max_queue)
        LOG.info(f"MQTT max_queued_messages set to {max_queue}")

        self.mqtt_properties = Properties(PacketTypes.PUBLISH)
        self.mqtt_properties.MessageExpiryInterval = 30  # in seconds
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 30 * 60  # in seconds
        LOG.info(
            f"Connecting to mqtt://{CONF.aprsd_mqtt_plugin.host_ip}:{CONF.aprsd_mqtt_plugin.host_port}"
        )
        self.client.connect(
            CONF.aprsd_mqtt_plugin.host_ip,
            port=CONF.aprsd_mqtt_plugin.host_port,
            # clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
            keepalive=60,
            # properties=properties
        )
        # Start the client's event loop thread to handle network I/O
        # This prevents blocking calls and ensures proper MQTT protocol handling
        self.client.loop_start()

        # Track publish failures for monitoring
        self.publish_failures = 0
        self.queue_full_count = 0
        # Track recent queue full events to detect persistent queue issues
        self.recent_queue_full = 0

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        LOG.info(
            f"Connected to mqtt://{CONF.aprsd_mqtt_plugin.host_ip}:"
            f"{CONF.aprsd_mqtt_plugin.host_port}/"
            f"{CONF.aprsd_mqtt_plugin.topic} (reason_code={reason_code})",
        )
        client.subscribe(CONF.aprsd_mqtt_plugin.topic)

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ):
        LOG.warning(f"MQTT client disconnected (reason_code={reason_code})")

    def stop(self):
        """Stop the MQTT client loop and disconnect cleanly."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                LOG.info("MQTT client stopped and disconnected")
            except Exception as e:
                LOG.error(f"Error stopping MQTT client: {e}")

    @hookimpl
    def filter(self, packet: packets.core.Packet):
        result = packets.NULL_MESSAGE
        if self.enabled:
            # packet is from a callsign in the watch list
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

        # Check if client is connected before attempting to publish
        # This prevents unnecessary JSON serialization when disconnected
        if not self.client.is_connected():
            # Client is disconnected, skip publishing to avoid blocking
            # The on_connect callback will handle reconnection
            LOG.warning("MQTT client is disconnected, skipping packet.")
            return packets.NULL_MESSAGE

        # If queue has been consistently full recently, skip JSON serialization
        # to avoid wasting CPU cycles when we know publish will fail
        # Reset counter after successful publishes
        if self.recent_queue_full > 500:
            # Queue has been consistently full, skip this packet entirely
            # This prevents slowdown from repeated failed publish attempts
            LOG.warning(
                f"MQTT publish queue has been consistently full for {self.recent_queue_full} packets. Skipping packet."
            )
            return packets.NULL_MESSAGE

        # Use a non-blocking publish to avoid potential blocking
        # Check return code to detect queue full scenarios
        try:
            # paho-mqtt's publish() returns immediately with loop_start()
            # but we need to check the return code for queue full errors
            result = self.client.publish(
                CONF.aprsd_mqtt_plugin.topic,
                payload=json.dumps(packet.raw_dict),
                qos=0,
            )

            # Check if publish was successful
            # result.rc will be mqtt.MQTT_ERR_QUEUE_SIZE if queue is full
            # result.rc will be mqtt.MQTT_ERR_SUCCESS (0) if queued successfully
            if result.rc == mqtt.MQTT_ERR_QUEUE_SIZE:
                self.queue_full_count += 1
                self.recent_queue_full += 1
                # Log warning every 100 queue full events to avoid log spam
                if self.queue_full_count % 100 == 1:
                    LOG.warning(
                        f"MQTT publish queue is full! Dropping packets. "
                        f"Total queue full events: {self.queue_full_count}. "
                        f"This indicates the MQTT broker is slow or network issues."
                    )
                # Skip further processing when queue is full to prevent blocking
                return packets.NULL_MESSAGE
            elif result.rc == mqtt.MQTT_ERR_SUCCESS:
                # Successful publish, reset recent queue full counter
                # This allows us to resume publishing when queue clears
                if self.recent_queue_full > 0:
                    self.recent_queue_full = max(0, self.recent_queue_full - 1)
            elif result.rc != mqtt.MQTT_ERR_SUCCESS:
                self.publish_failures += 1
                # Log error every 100 failures to avoid log spam
                if self.publish_failures % 100 == 1:
                    LOG.error(
                        f"MQTT publish failed with error code {result.rc}. "
                        f"Total failures: {self.publish_failures}"
                    )
        except Exception as e:
            self.publish_failures += 1
            # Only log exceptions occasionally to avoid log spam
            if self.publish_failures % 100 == 1:
                LOG.error(
                    f"MQTT publish exception: {e} (total failures: {self.publish_failures})"
                )

        # Now we can process
        return packets.NULL_MESSAGE
