
from dataclasses import dataclass, field
import databind.yaml as yaml
import typing as t


@dataclass
class Config:
  """
  Configuration of the bot.
  """

  #: Telegram bot token.
  token: str

  #: ID of the user(s) that can perform admin operations.
  admin_user_ids: t.Set[int] = field(default_factory=set)

  #: SqlAlchemy connect URL.
  database_spec: str = 'sqlite+pysqlite:///data/impfbot.db'

  #: Number of seconds between polling for updates from plugins.
  check_period_in_s: int = 20 * 60  # 20 minutes

  #: Number of hours to keep vaccination centers and their availability stored in the database.
  #: If there was no update within this period, the data is ignored/removd.
  retention_period_in_h: int = 1  # 1 hour

  #: Logging format.
  log_format: str = '[%(asctime)s - %(levelname)s - %(name)s]: %(message)s'

  #: ID of the Telegram chat to send logs of a certain level to.
  telegram_logger_chat_id: t.Optional[int] = None

  #: The log level to use for sending logs to the #telegram_logger_chat_id.
  telegram_logger_level: str = 'WARN'

  #: System-locale
  locale: str = 'de_DE'

  #: Port for the Prometheus metrics.
  metrics_port: int = 8000

  #: Host for the Prometheus metrics.
  metrics_host: str = 'localhost'

  @classmethod
  def load(cls, filename: str) -> 'Config':
    with open(filename) as fp:
      return yaml.from_stream(cls, fp)
