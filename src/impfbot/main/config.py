
from dataclasses import dataclass
import databind.yaml as yaml


@dataclass
class Config:
  token: str
  admin_chat_id: int = 56970700  # Niklas R.
  database_spec: str = 'sqlite+pysqlite:///data/impfbot.db'
  check_period_in_s: int = 20 * 60  # 20 minutes
  retention_period_in_h: int = 1  # 1 hour
  log_format: str = '[%(asctime)s - %(levelname)s - %(name)s]: %(message)s'

  @classmethod
  def load(cls, filename: str) -> 'Config':
    with open(filename) as fp:
      return yaml.from_stream(cls, fp)
