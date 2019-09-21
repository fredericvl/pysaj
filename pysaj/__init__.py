"""PySAJ interacts as a library to communicate with SAJ inverters"""
import xml.etree.ElementTree as ET
import urllib.request


class PySAJ(object):
    """Provides access to SAJ inverter data"""

    class ConnectionError(Exception):
        """Exception for connections"""
        def __init__(self):
            Exception.__init__(self,
                               "Connection to SAJ inverter not possible. " +
                               "Please check hostname/ip address.")

    def __init__(self, host):
        try:
            xml = ET.ElementTree(file=urllib.request.urlopen(
                                 "http://%s/real_time_data.xml" % host))
            root = xml.getroot()

            self.ac_power = root.find('p-ac').text
            self.e_today = root.find('e-today').text
            self.e_total = root.find('e-total').text
            self.t_today = root.find('t-today').text
            self.t_total = root.find('t-total').text
            self.maxpower = root.find('maxPower').text
            self.co2 = root.find('CO2').text
            self.temp = root.find('temp').text
            self.state = root.find('state').text
        except urllib.error.URLError:
            raise PySAJ.ConnectionError

    def getData(self):
        """Returns the data from SAJ inverter"""

        data = {'e_current': self.ac_power,
                'e_today': self.e_today,
                'e_total': self.e_total,
                't_today': self.t_today,
                't_total': self.t_total,
                'e_max_today': self.maxpower,
                'co2_reduced': self.co2,
                'temperature': self.temp,
                'state': self.state}
        return data
