
"""
Scans the available appointments for AstraZeneca and Johnson+Johnson vaccinations in Dachau,
Bavaria, DE that can be viewed at https://termin.dachau-med.de/impfungen01/ and
https://termin.dachau-med.de/impfungen02/.
"""

import bs4  # type: ignore
import datetime
import logging
import json
import re
import requests
import typing as t
from dataclasses import dataclass
from functools import reduce
from impfbot.model.api import AvailabilityInfo, VaccineRound, VaccineType, VaccinationCenter
from impfbot.polling.api import IPlugin, IVaccinationCenter

logger = logging.getLogger(__name__)

ASTRA_2_URL = 'https://termin.dachau-med.de/impfungen01/'
JNJ_URL = 'https://termin.dachau-med.de/impfungen02/'
BIONTECH_1_URL = 'https://termin.dachau-med.de/impfungen03/'
BIONTECH_2_URL = 'https://termin.dachau-med.de/impfung/'


def _parse_html(html: str) -> bs4.BeautifulSoup:
  return bs4.BeautifulSoup(html, features='html.parser')


def _get_salons(url: str, vaccine_round: VaccineRound) -> t.List['_Salon']:

  session = requests.Session()
  response = session.get(url)
  response.raise_for_status()
  soup = _parse_html(response.text)
  form = soup.find('form', id='salon-step-attendant')
  if not form:
    raise ValueError('form#salon-step-attendant not found')
  shop_list = soup.find('div', class_='sln-shop-list')
  if not shop_list:
    raise ValueError('div.sln-shop-list not found')
  shops = [{'id': opt.attrs['value'], 'name': opt.text.strip()} for opt in shop_list.find_all('option')]
  salon_extra = soup.find('script', id='salon-js-extra')
  if not salon_extra:
    raise ValueError('script#salon-js-extra not found')
  extra_data_json_payload = salon_extra.string.partition('=')[2].strip().rstrip(';')
  extra_data = json.loads(extra_data_json_payload)

  result: t.List[_Salon] = []
  for shop in shops:
    result.append(_Salon(
      id=shop['id'],
      name=shop['name'],
      url=url,
      location='Landkreis Dachau',
      ajax_url=extra_data['ajax_url'],
      ajax_nonce=extra_data['ajax_nonce'],
      vaccine_round=vaccine_round,
    ))

  return result


@dataclass
class _Salon:
  id: str
  name: str
  url: str
  location: str
  ajax_url: str
  ajax_nonce: str
  vaccine_round: VaccineRound

  def poll(self) -> AvailabilityInfo:
    response = requests.post(self.ajax_url, data={
      'sln[shop]': self.id,
      'sln_step_page': 'shop',
      'submit_shop': 'next',
      'action': 'salon',
      'method': 'salonStep',
      'security': self.ajax_nonce,
    })

    if 'Keine freien Termine' in response.text:
      return AvailabilityInfo(dates=[])

    content = response.json()['content']
    soup = bs4.BeautifulSoup(content, features='html.parser')
    data_node = soup.find(lambda t: 'data-intervals' in t.attrs)
    if not data_node:
      logger.error('Unable to find node with data-intervals attribute in page.\n\n%s\n', content)
      return AvailabilityInfo()

    intervals = json.loads(data_node.attrs['data-intervals'])
    dates = [datetime.datetime.strptime(d, '%Y-%m-%d').date() for d in intervals['dates']]

    return AvailabilityInfo(dates=dates)


class DachauMedPlugin(IPlugin):

  def get_vaccination_centers(self) -> t.Sequence['IVaccinationCenter']:
    salons = reduce(lambda a, b: a + b, [
      _get_salons(JNJ_URL, VaccineRound(VaccineType.JOHNSON_AND_JOHNSON, 0)) + \
      _get_salons(ASTRA_2_URL, VaccineRound(VaccineType.ASTRA_ZENECA, 2)) + \
      _get_salons(BIONTECH_1_URL, VaccineRound(VaccineType.BIONTECH, 1)) + \
      _get_salons(BIONTECH_2_URL, VaccineRound(VaccineType.BIONTECH, 2))
    ])

    # Transpose the salons and group them by location/salon name. Some salon names might be
    # slightly inconsistent, so we group them by a canonicalized name.
    salons_by_name: t.Dict[str, t.List[_Salon]] = {}
    for salon in salons:
      name = re.sub(r'[\(\)\s\./]+', '', salon.name).lower()
      salons_by_name.setdefault(name, []).append(salon)

    # Create a vaccination center for the salons grouped by name.
    centers: t.List[IVaccinationCenter] = []
    for name, salons in salons_by_name.items():
      centers.append(DachauMedVaccinationCenter(
        id=f'{__name__}:{name}',
        name=max((x.name for x in salons), key=len),  # Pick one with the longest name
        salons=salons,
      ))

    return centers


@dataclass
class DachauMedVaccinationCenter(IVaccinationCenter):

  id: str
  name: str
  salons: t.List[_Salon]

  def get_metadata(self) -> VaccinationCenter:
    # TODO(NiklasRosenstein): We need to provide different URLs for the different vaccine rounds.
    return VaccinationCenter(self.id, self.name, 'https://termin.dachau-med.de/', 'Landkreis Dachau')

  def check_availability(self) -> t.Dict[VaccineRound, AvailabilityInfo]:
    result = {}
    for salon in self.salons:
      try:
        result[salon.vaccine_round] = salon.poll()
      except Exception:
        logger.exception('An unexpected error occurred while polling salon %s', salon)
    return result
