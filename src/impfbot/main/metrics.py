
from prometheus_client import Counter, Gauge

users_num_registered = Gauge('users_num_registered', 'Number of users registered.')
users_num_subscribed = Gauge('users_num_subscribed', 'Number of users with active subscriptions.')
commands_executed = Counter('commands_executed', 'Number of commands executed', ['command'])
tgui_action_cache_size = Gauge('tgui_action_cache_size', 'Size of the tgui action cache.')
