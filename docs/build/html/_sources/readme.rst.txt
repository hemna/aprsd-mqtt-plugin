
APRSD MQTT Plugin
=================


.. image:: https://img.shields.io/pypi/v/aprsd-mqtt-plugin.svg
   :target: https://pypi.org/project/aprsd-mqtt-plugin/
   :alt: PyPI


.. image:: https://img.shields.io/pypi/status/aprsd-mqtt-plugin.svg
   :target: https://pypi.org/project/aprsd-mqtt-plugin/
   :alt: Status


.. image:: https://img.shields.io/pypi/pyversions/aprsd-mqtt-plugin
   :target: https://pypi.org/project/aprsd-mqtt-plugin
   :alt: Python Version


.. image:: https://img.shields.io/pypi/l/aprsd-mqtt-plugin
   :target: https://opensource.org/licenses/Apache%20Software%20License%202.0
   :alt: License



.. image:: https://img.shields.io/readthedocs/aprsd-mqtt-plugin/latest.svg?label=Read%20the%20Docs
   :target: https://aprsd-mqtt-plugin.readthedocs.io/
   :alt: Read the Docs


.. image:: https://github.com/hemna/aprsd-mqtt-plugin/workflows/Tests/badge.svg
   :target: https://github.com/hemna/aprsd-mqtt-plugin/actions?workflow=Tests
   :alt: Tests


.. image:: https://codecov.io/gh/hemna/aprsd-mqtt-plugin/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/hemna/aprsd-mqtt-plugin
   :alt: Codecov



.. image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit


----

..

   [!WARNING]
   Legal operation of this software requires an amateur radio license and a valid call sign.

   [!NOTE]
   Star this repo to follow our progress! This code is under active development, and contributions are both welcomed and appreciated. See `CONTRIBUTING.md <https://github.com/hemna/aprsd-mqtt-plugin/blob/master/CONTRIBUTING.md>`_ for details.


Features
--------

The APRSD MQTT Plugin publishes APRS packets to an MQTT broker, allowing you to integrate APRSD with MQTT-based systems. Key features include:


* **MQTT Publishing**\ : Automatically publishes all received APRS packets to a configured MQTT topic
* **JSON Format**\ : Packets are published as JSON for easy consumption by other systems
* **Configurable Broker**\ : Connect to any MQTT broker (local or remote)
* **Authentication Support**\ : Optional username/password authentication for MQTT broker
* **Real-time Integration**\ : Enables real-time APRS data streaming to MQTT subscribers

Requirements
------------


* ``aprsd >= 3.0.0``
* A running APRSD instance
* Access to an MQTT broker (Mosquitto, HiveMQ, EMQX, etc.)

Installation
------------

You can install *APRSD MQTT Plugin* via `pip <https://pip.pypa.io/>`_ from `PyPI <https://pypi.org/>`_\ :

.. code-block:: console

   $ pip install aprsd-mqtt-plugin

Or using ``uv``\ :

.. code-block:: console

   $ uv pip install aprsd-mqtt-plugin

Configuration
-------------

Before using the MQTT plugin, you need to configure it in your APRSD configuration file.
Generate a sample configuration file if you haven't already:

.. code-block:: console

   $ aprsd sample-config

This will create a configuration file at ``~/.config/aprsd/aprsd.conf`` (or ``aprsd.yml``\ ).

MQTT Plugin Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^

Add the following section to your APRSD configuration file to configure the MQTT plugin:

.. code-block:: yaml

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

Example Configuration
^^^^^^^^^^^^^^^^^^^^^

Here's a complete example configuration:

.. code-block:: yaml

   [aprsd_mqtt_plugin]
   enabled = True
   host_ip = mqtt.example.com
   host_port = 1883
   topic = aprsd/packets
   user = mqtt_user
   password = mqtt_password

Enable the Plugin
^^^^^^^^^^^^^^^^^

To enable the plugin, add it to the ``enabled_plugins`` section of your APRSD configuration:

.. code-block:: ini

   [aprsd]
   enabled_plugins = aprsd_mqtt_plugin.aprsd_mqtt_plugin.MQTTPlugin

Usage
-----

Once installed and configured, the MQTT plugin will automatically start when you run ``aprsd server``.

How It Works
^^^^^^^^^^^^

The plugin:


#. Connects to the configured MQTT broker on startup
#. Subscribes to the configured topic
#. Publishes all received APRS packets as JSON to the MQTT topic
#. Maintains a persistent connection to the broker

Packet Format
^^^^^^^^^^^^^

Packets are published as JSON with the following structure:

.. code-block:: json

   {
     "from": "CALLSIGN",
     "to": "DESTINATION",
     "message_text": "Message content",
     "path": ["WIDE1-1", "WIDE2-2"],
     "timestamp": "2024-01-01T12:00:00"
   }

Note: Additional fields may be present in the JSON payload.

Verifying It's Working
^^^^^^^^^^^^^^^^^^^^^^

After starting APRSD, check the logs for messages like:

.. code-block::

   INFO: Connecting to mqtt://localhost:1883
   INFO: Connected to mqtt://localhost:1883/aprsd/packets (0)

You can also subscribe to the MQTT topic using an MQTT client:

.. code-block:: console

   $ mosquitto_sub -h localhost -t aprsd/packets

Or using ``mqtt-cli``\ :

.. code-block:: console

   $ mqtt sub -t aprsd/packets

Integration Examples
^^^^^^^^^^^^^^^^^^^^

**Home Assistant Integration:**

.. code-block:: yaml

   mqtt:
     sensor:
       - name: "APRS Packet"
         state_topic: "aprsd/packets"
         value_template: "{{ value_json.message_text }}"

**Node-RED Integration:**

Connect an MQTT input node to ``aprsd/packets`` and parse the JSON payload.

**Custom Application:**

Subscribe to the MQTT topic and process the JSON packets in your application.

For more details, see the `Command-line Reference <https://aprsd-mqtt-plugin.readthedocs.io/en/latest/usage.html>`_.

Contributing
------------

Contributions are very welcome. To learn more, see the `Contributor Guide <CONTRIBUTING.rst>`_.

License
-------

Distributed under the terms of the `Apache Software License 2.0 license <https://opensource.org/licenses/Apache%20Software%20License%202.0>`_\ ,
*APRSD MQTT Plugin* is free and open source software.

Issues
------

If you encounter any problems,
please `file an issue <https://github.com/hemna/aprsd-mqtt-plugin/issues>`_ along with a detailed description.

Credits
-------

This project was generated from `@hemna <https://github.com/hemna>`_\ 's `APRSD Plugin Python Cookiecutter <https://github.com/hemna/cookiecutter-aprsd-plugin>`_ template.
