#!/usr/bin/env python
"""Tests for MQTTRawPlugin class."""

import pytest
import queue
from unittest.mock import MagicMock, patch


class TestMQTTRawPlugin:
    """Tests for the MQTTRawPlugin class."""

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_inherits_from_base_and_thread(self, mock_conf, mock_mqtt_client):
        """Test that MQTTRawPlugin inherits from MQTTPluginBase and APRSDFilterThread."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin, MQTTPluginBase
        from aprsd.threads.rx import APRSDFilterThread

        assert issubclass(MQTTRawPlugin, MQTTPluginBase)
        assert issubclass(MQTTRawPlugin, APRSDFilterThread)

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_constructor_accepts_packet_queue(self, mock_conf, mock_mqtt_client):
        """Test that constructor accepts packet_queue parameter."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.raw_topic = "aprsd/raw"
        mock_conf.callsign = "TEST"

        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance

        packet_queue = queue.Queue()
        plugin = MQTTRawPlugin(packet_queue)

        assert plugin.packet_queue is packet_queue

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_loop_publishes_raw_string(self, mock_conf, mock_mqtt_client):
        """Test that loop() pulls from queue and publishes raw string."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin
        import paho.mqtt.client as mqtt

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.raw_topic = "aprsd/raw"
        mock_conf.callsign = "TEST"

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
        assert mock_client_instance.publish.called
        call_args = mock_client_instance.publish.call_args
        assert call_args[0][0] == "aprsd/raw"
        assert call_args[1]["payload"] == raw_packet

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_loop_handles_empty_queue(self, mock_conf, mock_mqtt_client):
        """Test that loop() handles empty queue gracefully."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTRawPlugin

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.raw_topic = "aprsd/raw"
        mock_conf.callsign = "TEST"

        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance

        packet_queue = queue.Queue()  # Empty queue

        plugin = MQTTRawPlugin(packet_queue)
        result = plugin.loop()

        # Should return True to keep thread running
        assert result is True
        # Should not have called publish since queue was empty
        mock_client_instance.publish.assert_not_called()
