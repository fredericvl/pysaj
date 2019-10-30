"""PySAJ interacts as a library to communicate with SAJ inverters"""
import aiohttp
import asyncio
import concurrent
import csv
from io import StringIO
from datetime import date
import logging
import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)

MAPPER_STATES = {
    "0": "Not connected",
    "1": "Waiting",
    "2": "Normal",
    "3": "Error",
    "4": "Upgrading",
}

URL_PATH_ETHERNET = "real_time_data.xml"
URL_PATH_WIFI = "status/status.php"


class Sensor(object):
    """Sensor definition"""

    def __init__(self, key, csv_1_key, csv_2_key, factor, name, unit='',
                 per_day_basis=False, per_total_basis=False):
        self.key = key
        self.csv_1_key = csv_1_key
        self.csv_2_key = csv_2_key
        self.factor = factor
        self.name = name
        self.unit = unit
        self.value = None
        self.per_day_basis = per_day_basis
        self.per_total_basis = per_total_basis
        self.date = date.today()


class Sensors(object):
    """SAJ sensors"""

    def __init__(self, wifi=False):
        self.__s = []
        self.add(
            (
                Sensor("p-ac", 11, 23, "", "current_power", "W"),
                Sensor("e-today", 3, 3, "/100", "today_yield", "kWh", True),
                Sensor("e-total", 1, 1, "/100", "total_yield", "kWh", False,
                       True),
                Sensor("t-today", 4, 4, "/10", "today_time", "h", True),
                Sensor("t-total", 2, 2, "/10", "total_time", "h", False, True),
                Sensor("CO2", 21, 33, "/10", "total_co2_reduced", "kg", False,
                       True),
                Sensor("temp", 20, 32, "/10", "temperature", "°C"),
                Sensor("state", 22, 34, "", "state")
            )
        )
        if not wifi:
            self.add(
                Sensor("maxPower", -1, -1, "", "today_max_current", "W", True)
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

    def __init__(self, host, wifi=False, username='admin', password='admin'):
        self.host = host
        self.wifi = wifi
        self.username = username
        self.password = password

        self.url = "http://{0}/".format(self.host)
        if self.wifi:
            if (len(self.username) > 0
               and len(self.password) > 0):
                self.url = "http://{0}:{1}@{2}/".format(self.username,
                                                        self.password,
                                                        self.host)
                self.url += URL_PATH_WIFI
        else:
            self.url += URL_PATH_ETHERNET

    async def read(self, sensors):
        """Returns necessary sensors from SAJ inverter"""

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout,
                                             raise_for_status=True) as session:
                async with session.get(self.url) as response:
                    data = await response.text()

                    if self.wifi:
                        csv_data = StringIO(data)
                        reader = csv.reader(csv_data)
                        ncol = len(next(reader))
                        csv_data.seek(0)

                        values = []

                        for row in reader:
                            for (i, v) in enumerate(row):
                                values.append(v)

                        for sen in sensors:
                            if ncol < 24:
                                if sen.csv_1_key != -1:
                                    v = values[sen.csv_1_key]
                                else:
                                    v = None
                            else:
                                if sen.csv_2_key != -1:
                                    v = values[sen.csv_2_key]
                                else:
                                    v = None

                            if v is not None:
                                if sen.name == "state":
                                    sen.value = MAPPER_STATES[v]
                                else:
                                    sen.value = eval(
                                        "{0}{1}".format(v, sen.factor)
                                    )
                                sen.date = date.today()
                    else:
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
        except (aiohttp.client_exceptions.ClientConnectorError,
                concurrent.futures._base.TimeoutError):
            # Connection to inverter not possible.
            # This can be "normal" - so warning instead of error - as SAJ
            # inverters are powered by DC and thus have no power after the sun
            # has set.
            _LOGGER.warning("Connection to SAJ inverter is not possible. " +
                            "The inverter may be offline due to darkness. " +
                            "Otherwise check host/ip address.")
            return False
        except aiohttp.client_exceptions.ClientResponseError as err:
            # 401 Unauthorized: wrong username/password
            if err.status == 401:
                raise UnauthorizedException(err)
            else:
                raise UnexpectedResponseException(err)
        except ET.ParseError:
            # XML is not valid or even no XML at all
            raise UnexpectedResponseException(
                str.format("No valid XML received from {0}", self.host)
            )
        except KeyError:
            # XML received does not have all the required elements
            raise UnexpectedResponseException(
                str.format("SAJ sensor key {0} not found, inverter not " +
                           "compatible?", sen.key)
            )
        except IndexError:
            # CSV received does not have all the required elements
            raise UnexpectedResponseException(
                str.format(
                    "SAJ sensor name {0} at CSV position {1} not found, " +
                    "inverter not compatible?",
                    sen.name,
                    sen.csv_1_key if ncol < 24 else sen.csv_2_key
                )
            )


class UnauthorizedException(Exception):
    """Exception for Unauthorized 401 status code"""
    def __init__(self, message):
        Exception.__init__(self, message)


class UnexpectedResponseException(Exception):
    """Exception for unexpected status code"""
    def __init__(self, message):
        Exception.__init__(self, message)
