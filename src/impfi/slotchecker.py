
import abc
import enum
import re
import typing as t
from dataclasses import dataclass

import requests


class VaccineType(enum.Enum):
  UNKNOWN = enum.auto()
  JOHNSON_AND_JOHNSON = enum.auto()
  ASTRAZENECA = enum.auto()
  BIONTECH =  enum.auto()


@dataclass
class SlotResponse:
  content: str


class SlotChecker(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_description(self) -> str: ...

  @abc.abstractmethod
  def check_available_slots(self) -> SlotResponse: ...


@dataclass
class DachauMedSlotChecker(SlotChecker):
  """
  Can check for available slots at https://termin.dachau-med.de.
  """

  class Office(enum.Enum):
    MVZ_OG3 = '18'
    BERGKIRCHEN = '31'
    MVZ_OG1 = '33'
    ALTSTADT = '19'
    SULZEMOOS = '35'
    NEUFAHRN = '29'
    ECHING = '27'
    ALLACH = '39'
    REMBOLD_RINCK_PFISTER_GIULIANI = '15087'

  class BaseUrls(enum.Enum):
    JOHNSON_AND_JOHNSON = 'https://termin.dachau-med.de/impfungen02/'  # Johnson & Johnson

  name: str
  office_id: str
  base_url: str
  ajax_url: str = None

  def __post_init__(self):
    if not self.ajax_url:
      self.ajax_url = self.base_url.rstrip('/') + '/wp-admin/admin-ajax.php?lang=de'

  @classmethod
  def all_offices(cls) -> t.List[SlotChecker]:
    result = []
    for vaccine_base_url in cls.BaseUrls:
      for office in cls.Office:
        result.append(cls(office.name, office.value, vaccine_base_url.value))
    return result

  # SlotChecker
  def get_description(self) -> str:
    return self.name

  # SlotChecker
  def check_available_slots(self) -> SlotResponse:
    session = requests.Session()
    response = session.get(self.base_url)
    nonce = re.search(r'ajax_nonce":\s*"(\w+)', response.text).group(1)
    assert nonce is not None
    response = session.post(self.ajax_url, data={
      'sln[shop]': '18',
      'sln_step_page': 'shop',
      'submit_shop': 'next',
      'action': 'salon',
      'method': 'salonStep',
      'security': nonce,
    })
    if 'Keine freien Termine' in response.text:
      return None
    return SlotResponse(response.text)

