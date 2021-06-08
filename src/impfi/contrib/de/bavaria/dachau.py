
"""
Scans the available appointments for AstraZeneca and Johnson+Johnson vaccinations in Dachau,
Bavaria, DE that can be viewed at https://termin.dachau-med.de/impfungen01/ and
https://termin.dachau-med.de/impfungen02/.
"""

import bs4  # type: ignore
import datetime
import json
import requests
import typing as t
from dataclasses import dataclass
from impfi.api import AvailabilityInfo, IPlugin, IVaccinationCenter, VaccineType

ASTRA_URL = 'https://termin.dachau-med.de/impfungen01/'
JNJ_URL = 'https://termin.dachau-med.de/impfungen02/'


def _parse_html(html: str) -> bs4.BeautifulSoup:
  return bs4.BeautifulSoup(html, features='html.parser')


def _get_vaccination_centers_for(url: str, vaccine_type: VaccineType) -> t.List['DachauMedVaccinationCenter']:
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

  result: t.List[DachauMedVaccinationCenter] = []
  for shop in shops:
    result.append(DachauMedVaccinationCenter(
      vaccine_type, shop['name'], shop['id'], url, extra_data['ajax_url'],
      extra_data['ajax_nonce']))

  return result


class DachauMedPlugin(IPlugin):

  def get_vaccination_centers(self) -> t.Sequence['IVaccinationCenter']:
    return _get_vaccination_centers_for(ASTRA_URL, VaccineType.AstraZeneca) + \
      _get_vaccination_centers_for(JNJ_URL, VaccineType.JohnsonAndJohnson)


@dataclass
class DachauMedVaccinationCenter(IVaccinationCenter):

  vaccine_type: VaccineType
  name: str
  salon_id: str
  url: str
  ajax_url: str
  ajax_none: str

  @property
  def uid(self) -> str:  # type: ignore
    return f'{__name__}:{self.vaccine_type.name}:{self.salon_id}'

  @property
  def location(self) -> str:  # type: ignore
    return 'Germany, Bavaria, Landkreis Dachau'

  def check_availability(self) -> t.Dict[VaccineType, AvailabilityInfo]:

    response = requests.post(self.ajax_url, data={
      'sln[shop]': self.salon_id,
      'sln_step_page': 'shop',
      'submit_shop': 'next',
      'action': 'salon',
      'method': 'salonStep',
      'security': self.ajax_none,
    })

    if 'Keine freien Termine' in response.text:
      return {}

    content = response.json()['content']
    soup = bs4.BeautifulSoup(content, features='html.parser')
    data_node = soup.find(lambda t: 'data-intervals' in t.attrs)
    intervals = json.loads(data_node.attrs['data-intervals'])
    dates = [datetime.datetime.strptime(d, '%Y-%m-%d').date() for d in intervals['dates']]
    return {self.vaccine_type: AvailabilityInfo(dates=dates, not_available_until=None)}
