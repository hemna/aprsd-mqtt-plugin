#!/usr/bin/env python
"""Tests for MQTTPlugin class."""

from unittest.mock import MagicMock, patch


def test_package_exports_both_plugins():
    """Test that package exports both plugin classes."""
    from aprsd_mqtt_plugin import MQTTPlugin, MQTTRawPlugin

    assert MQTTPlugin is not None
    assert MQTTRawPlugin is not None


class TestMQTTPlugin:
    """Tests for the refactored MQTTPlugin class."""

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_inherits_from_base(self, mock_conf, mock_mqtt_client):
        """Test that MQTTPlugin inherits from MQTTPluginBase."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPlugin, MQTTPluginBase

        assert issubclass(MQTTPlugin, MQTTPluginBase)

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_setup_calls_base_setup(self, mock_conf, mock_mqtt_client):
        """Test that setup() calls setup_mqtt_client()."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPlugin

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.topic = "aprsd/packets"
        mock_conf.callsign = "TEST"

        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance

        plugin = MQTTPlugin()
        plugin.setup()

        assert plugin.enabled is True
        # Verify connect was called (at least once)
        assert mock_client_instance.connect.called

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_process_publishes_json(self, mock_conf, mock_mqtt_client):
        """Test that process() publishes packet as JSON to topic."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPlugin
        import paho.mqtt.client as mqtt

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.topic = "aprsd/packets"
        mock_conf.callsign = "TEST"

        mock_client_instance = MagicMock()
        mock_client_instance.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client_instance.publish.return_value = mock_publish_result
        mock_mqtt_client.return_value = mock_client_instance

        plugin = MQTTPlugin()
        plugin.setup()

        # Create a mock packet
        mock_packet = MagicMock()
        mock_packet.raw_dict = {"from": "N0CALL", "to": "APRS"}

        plugin.process(mock_packet)

        # Verify publish was called with the topic
        assert mock_client_instance.publish.called
        call_args = mock_client_instance.publish.call_args
        assert call_args[0][0] == "aprsd/packets"
