
import collections
import logging
import typing as t
import yaml

logger = logging.getLogger(__name__)


class Template(str):

  def __call__(self, **params) -> str:
    return self.replace('\\\n', '').format_map(collections.defaultdict(lambda: '<?>', params))


class Locale:

  def __init__(self, filename: str) -> None:
    self._filename = filename
    self._data = yaml.safe_load(open(filename))  # TODO

  def get(self, key: str, **kwargs) -> str:
    if key not in self._data:
      logger.warn('Missing locale key in "%s": %s', self._filename, key)
      return '<?>'
    return Template(self._data[key])(**kwargs)


_gl: t.Optional[Locale] = None


def load(filename: str) -> None:
  global _gl
  _gl = Locale(filename)


def get(key: str, **kwargs) -> str:
  assert _gl, 'Global locale not initialized'
  return _gl.get(key, **kwargs)
