
import typing as t
from impfbot.model.api import AvailabilityInfo, VaccineRound, VaccineType, VaccinationCenter
from impfbot.polling.api import IPlugin, IVaccinationCenter


class DevelopPlugin(IPlugin):

  def get_vaccination_centers(self) -> t.Sequence['IVaccinationCenter']:
      return super().get_vaccination_centers()