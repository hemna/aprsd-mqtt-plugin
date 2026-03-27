#!/usr/bin/env python
"""Tests for MQTTPluginBase class."""

from unittest.mock import MagicMock, patch


class TestMQTTPluginBase:
    """Tests for the MQTTPluginBase class."""

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_setup_mqtt_client_creates_client(self, mock_conf, mock_mqtt_client):
        """Test that setup_mqtt_client creates and connects MQTT client."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase

        # Configure mock
        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.aprsd_mqtt_plugin.password = None
        mock_conf.callsign = "TEST"

        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance

        base = MQTTPluginBase()
        result = base.setup_mqtt_client()

        assert result is True
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.loop_start.assert_called_once()

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_publish_success(self, mock_conf, mock_mqtt_client):
        """Test that publish sends to MQTT broker."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase
        import paho.mqtt.client as mqtt

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.callsign = "TEST"

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

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_publish_skips_when_disconnected(self, mock_conf, mock_mqtt_client):
        """Test that publish skips when client is disconnected."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = "localhost"
        mock_conf.aprsd_mqtt_plugin.host_port = 1883
        mock_conf.aprsd_mqtt_plugin.user = None
        mock_conf.callsign = "TEST"

        mock_client_instance = MagicMock()
        mock_client_instance.is_connected.return_value = False
        mock_mqtt_client.return_value = mock_client_instance

        base = MQTTPluginBase()
        base.setup_mqtt_client()

        result = base.publish("test/topic", b"test payload")

        assert result is False
        mock_client_instance.publish.assert_not_called()

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_setup_returns_false_when_disabled(self, mock_conf, mock_mqtt_client):
        """Test that setup_mqtt_client returns False when disabled."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase

        mock_conf.aprsd_mqtt_plugin.enabled = False

        base = MQTTPluginBase()
        result = base.setup_mqtt_client()

        assert result is False
        mock_mqtt_client.assert_not_called()

    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.mqtt.Client")
    @patch("aprsd_mqtt_plugin.aprsd_mqtt_plugin.CONF")
    def test_setup_returns_false_when_no_host(self, mock_conf, mock_mqtt_client):
        """Test that setup_mqtt_client returns False when host_ip not set."""
        from aprsd_mqtt_plugin.aprsd_mqtt_plugin import MQTTPluginBase

        mock_conf.aprsd_mqtt_plugin.enabled = True
        mock_conf.aprsd_mqtt_plugin.host_ip = None

        base = MQTTPluginBase()
        result = base.setup_mqtt_client()

        assert result is False
        mock_mqtt_client.assert_not_called()
