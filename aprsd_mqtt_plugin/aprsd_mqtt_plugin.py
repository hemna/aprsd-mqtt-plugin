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

        self.mqtt_properties = Properties(PacketTypes.PUBLISH)
        self.mqtt_properties.MessageExpiryInterval = 30  # in seconds
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 30 * 60  # in seconds
        LOG.info(f"Connecting to mqtt://{CONF.aprsd_mqtt_plugin.host_ip}:{CONF.aprsd_mqtt_plugin.host_port}")
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

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        LOG.info(
            f"Connected to mqtt://{CONF.aprsd_mqtt_plugin.host_ip}:"
            f"{CONF.aprsd_mqtt_plugin.host_port}/"
            f"{CONF.aprsd_mqtt_plugin.topic} (reason_code={reason_code})",
        )
        client.subscribe(CONF.aprsd_mqtt_plugin.topic)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
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
                        self.__class__, ex,
                    ),
                )
            if result:
                self.tx_inc()

        return result

    def process(self, packet: packets.core.Packet):
        if self.tx_count % 50 == 0:
            LOG.debug(
                f"MQTTPlugin Publishing packet ({self.tx_count}) to mqtt://"
                f"{CONF.aprsd_mqtt_plugin.host_ip}:{CONF.aprsd_mqtt_plugin.host_port}"
                f"/{CONF.aprsd_mqtt_plugin.topic}",
            )
        self.client.publish(
            CONF.aprsd_mqtt_plugin.topic,
            # payload=packet.to_json(),
            payload=json.dumps(packet.raw_dict),
            qos=0,
            # qos=2,
            # properties=self.mqtt_properties
        )

        # Now we can process
        return packets.NULL_MESSAGE
