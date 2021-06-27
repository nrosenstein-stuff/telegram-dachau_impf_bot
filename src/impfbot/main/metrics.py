
from prometheus_client import Counter, Gauge
from impfbot import polling
from impfbot import model
from impfbot.model.db import ISessionProvider

users_num_registered = Gauge('users_num_registered', 'Number of users registered.')
users_num_subscribed = Gauge('users_num_subscribed', 'Number of users with active subscriptions.')
commands_executed = Counter('commands_executed', 'Number of commands executed', ['command'])
tgui_action_cache_size = Gauge('tgui_action_cache_size', 'Size of the tgui action cache.')
number_of_dates_with_available_vaccination_appointments = Gauge(
  'number_of_dates_with_available_vaccination_appointments', '',
  ['vaccine_type', 'vaccine_round', 'vaccination_center_id', 'vaccination_center_name',
   'vaccination_center_location'])


class AvailabilityMetrics(polling.IDataReceiver):
  """
  Populates the :data:`number_of_dates_with_available_vaccination_appointments` metric.
  """

  def __init__(self, session: ISessionProvider, avail: model.IAvailabilityStore) -> None:
    self.session = session
    self.avail = avail

  def publish_all(self) -> None:
    with self.session:
      for center in self.avail.search_vaccination_centers(None):
        for vaccine_round, data in self.avail.get_per_vaccine_round_availability(center.id):
          self._publish_metrics(center, vaccine_round, data)

  def on_availability_info_ready(self,
    center: polling.IVaccinationCenter,
    vaccine_round: model.VaccineRound,
    data: model.AvailabilityInfo
  ) -> None:

    vcenter = center.get_metadata()
    self._publish_metrics(vcenter, vaccine_round, data)

  def _publish_metrics(self,
    center: model.VaccinationCenter,
    vaccine_round: model.VaccineRound,
    data: model.AvailabilityInfo
  ) -> None:

    number_of_dates_with_available_vaccination_appointments.labels(
      vaccine_round.type.name, vaccine_round.round, center.id, center.name, center.location).set(len(data.dates))
