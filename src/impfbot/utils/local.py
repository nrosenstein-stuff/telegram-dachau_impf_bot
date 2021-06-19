
import threading
import typing as t

T = t.TypeVar('T')


class LocalList(t.Generic[T]):

  def __init__(self) -> None:
    self._local = threading.local()

  def __bool__(self) -> bool:
    return bool(self._list())

  def _list(self) -> t.List[T]:
    result = getattr(self._local, 'val', None)
    if result is None:
      self._local.val = result = []
    return result

  def append(self, item: T) -> None:
    return self._list().append(item)

  def pop(self) -> T:
    return self._list().pop()

  def last(self) -> T:
    return self._list()[-1]
