"""PySAJ interacts as a library to communicate with SAJ inverters"""
import aiohttp
import asyncio
from datetime import date
import logging
import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)


class Sensor(object):
    """Sensor definition"""

    def __init__(self, key, name, unit='', per_day_basis=False,
                 per_total_basis=False):
        self.key = key
        self.name = name
        self.unit = unit
        self.value = None
        self.per_day_basis = per_day_basis
        self.per_total_basis = per_total_basis
        self.date = date.today()


class Sensors(object):
    """SAJ sensors"""

    def __init__(self):
        self.__s = []
        self.add(
            (
                Sensor("p-ac", "current_power", "W"),
                Sensor("e-today", "today_yield", "kWh", True),
                Sensor("e-total", "total_yield", "kWh", False, True),
                Sensor("maxPower", "today_max_current", "W", True),
                Sensor("t-today", "today_time", "h", True),
                Sensor("t-total", "total_time", "h", False, True),
                Sensor("CO2", "total_co2_reduced", "kg", False, True),
                Sensor("temp", "temperature", "°C"),
                Sensor("state", "state")
            )
        )

    def __len__(self):
        """Length."""
        return len(self.__s)

    def __contains__(self, key):
        """Get a sensor using either the name or key."""
        try:
            if self[key]:
                return True
        except KeyError:
            return False

    def __getitem__(self, key):
        """Get a sensor using either the name or key."""
        for sen in self.__s:
            if sen.name == key or sen.key == key:
                return sen
        raise KeyError(key)

    def __iter__(self):
        """Iterator."""
        return self.__s.__iter__()

    def add(self, sensor):
        """Add a sensor, warning if it exists."""
        if isinstance(sensor, (list, tuple)):
            for sss in sensor:
                self.add(sss)
            return

        if not isinstance(sensor, Sensor):
            raise TypeError("pysaj.Sensor expected")

        if sensor.name in self:
            old = self[sensor.name]
            self.__s.remove(old)
            _LOGGER.warning("Replacing sensor %s with %s", old, sensor)

        if sensor.key in self:
            _LOGGER.warning("Duplicate SAJ sensor key %s", sensor.key)

        self.__s.append(sensor)


class SAJ(object):
    """Provides access to SAJ inverter data"""

    def __init__(self, host):
        self.host = host

    async def read(self, sensors):
        """Returns necessary sensors from SAJ inverter"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://%s/real_time_data.xml" %
                                       self.host) as xmlfile:
                    data = await xmlfile.text()
                    xml = ET.fromstring(data)

                    for sen in sensors:
                        find = xml.find(sen.key)
                        if find is None:
                            raise KeyError
                        sen.value = find.text
                        sen.date = date.today()
                        _LOGGER.debug("Got new value for sensor %s: %s",
                                      sen.name, sen.value)

                    return True
        except aiohttp.client_exceptions.ClientConnectorError:
            # Connection to inverter not possible.
            # This can be "normal" - so warning instead of error - as SAJ
            # inverters are powered by DC and thus have no power after the sun
            # has set.
            _LOGGER.warning("Connection to SAJ inverter is not possible. " +
                            "The inverter may be offline due to darkness. " +
                            "Otherwise check host/ip address.")
            return False
        except ET.ParseError:
            # XML is not valid or even no XML at all
            _LOGGER.error("No valid XML received from %s", self.host)
            return False
        except KeyError:
            # XML received does not have all the required elements
            _LOGGER.error("SAJ sensor key %s not found, inverter not " +
                          "compatible?", sen.key)
            return False
