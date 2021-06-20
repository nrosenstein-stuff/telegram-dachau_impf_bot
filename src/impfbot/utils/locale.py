
import collections
import logging
import typing as t
import yaml  # type: ignore

logger = logging.getLogger(__name__)


class Template(str):

  def __call__(self, **params) -> str:
    return self.replace('\\\n', '').format_map(collections.defaultdict(lambda: '<?>', params))


class Locale:

  def __init__(self, filename: str) -> None:
    self._filename = filename
    self._data: t.Dict[str, str] = yaml.safe_load(open(filename))  # TODO

  def get(self, key: str, **kwargs) -> str:
    data = self._data
    for part in key.split('.'):
      if not isinstance(data, t.Mapping) or part not in data:
        logger.warn('Missing locale key in "%s": %s (%s)', self._filename, key, part)
        return '<?>'
      data = data[part]
    if not isinstance(data, str):
      logger.warn('Missing locale key in "%s": %s (%s)', self._filename, key, part)
      return '<?>'
    return Template(data)(**kwargs)


_gl: t.Optional[Locale] = None


def load(filename: str) -> None:
  global _gl
  _gl = Locale(filename)


def get(key: str, **kwargs) -> str:
  assert _gl, 'Global locale not initialized'
  return _gl.get(key, **kwargs)
