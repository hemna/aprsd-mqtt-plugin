from oslo_config import cfg


plugin_group = cfg.OptGroup(
    name="aprsd_mqtt_plugin",
    title="APRSD Slack Plugin settings",
)

plugin_opts = [
    cfg.BoolOpt(
        "enabled",
        default=False,
        help="Enable the plugin?",
    ),
    cfg.StrOpt(
        "host_ip",
        default=None,
        help="The hostname/ip address of the mqtt server",
    ),
    cfg.IntOpt(
        "host_port",
        default=1883,
        help="The port to of the MQTT server",
    ),
    cfg.StrOpt(
        "user",
        default=None,
        help="The mqtt username to use",
    ),
    cfg.StrOpt(
        "password",
        default=None,
        help="the mqtt password",
    ),
    cfg.StrOpt(
        "topic",
        default="aprsd/packet",
        help="The MQTT Topic to subscribe for messages",
    ),
]

ALL_OPTS = plugin_opts


def register_opts(cfg):
    cfg.register_group(plugin_group)
    cfg.register_opts(ALL_OPTS, group=plugin_group)


def list_opts():
    return {
        plugin_group.name: plugin_opts,
    }
