"""A data accessor for network-connected solar panels.

This module uses the Modbus TCP protocol to connect to and read from solar
panels connected to the UW network. The configuration for these panels is
heterogeneous, so register mappings for each different configuration are
provided in Excel spreadsheets.
"""

import time
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.payload import BinaryPayloadDecoder
from collector import model

# The number of bits per register (2 bytes = 16 bits).
BITS_PER_REGISTER = 16

# A mapping from metric data type to decoding method.
DATA_TYPE_TO_DECODER_MAP = {
  model.MetricDataType.UINT8: BinaryPayloadDecoder.decode_8bit_uint,
  model.MetricDataType.UINT16: BinaryPayloadDecoder.decode_16bit_uint,
  model.MetricDataType.UINT32: BinaryPayloadDecoder.decode_32bit_uint,
  model.MetricDataType.UINT64: BinaryPayloadDecoder.decode_64bit_uint,
  model.MetricDataType.INT8: BinaryPayloadDecoder.decode_8bit_int,
  model.MetricDataType.INT16: BinaryPayloadDecoder.decode_16bit_int,
  model.MetricDataType.INT32: BinaryPayloadDecoder.decode_32bit_int,
  model.MetricDataType.INT64: BinaryPayloadDecoder.decode_64bit_int,
  model.MetricDataType.FLOAT32: BinaryPayloadDecoder.decode_32bit_float,
  model.MetricDataType.FLOAT64: BinaryPayloadDecoder.decode_64bit_float
}


class PanelAccessor:
  """A data accessor for solar panels."""

  def __init__(self, host, metrics, retries, retry_wait_time):
    """Creates a new solar panel accessor.

    Args:
      host: The TCP host.
      metrics: A mapping of metric names to metric metadata for this panel.
      retries: The number of times to retry a Modbus RPC.
      retry_wait_time: The delay in seconds between Modbus RPC retries.
    """
    self._modbus_client = ModbusTcpClient(host)
    self._metrics = metrics
    self._retries = retries
    self._retry_wait_time = retry_wait_time

  @property
  def metrics(self):
    return self._metrics

  def has_metric(self, name):
    """Checks if a particular metric is supported by this panel.

    Args:
      name: The metric name.

    Returns:
      Whether information about the metric is known.
    """
    return name in self._metrics

  def get_metric(self, name):
    """Gets the current value of a particular metric.

    This method queries the solar panel through its Modbus interface. The
    metric name is mapped to a Modbus address, and the registers at that
    address are retrieved and decoded.

    Args:
      name: The metric name.

    Returns:
      The current value of the metric.
    """
    metric = self._metrics[name]
    for i in range(0, self._retries):
      result = None
      try:
        result = self._modbus_client.read_holding_registers(
          metric.address, metric.size, unit=0x01)
      except ConnectionException as e:
        if i == self._retries - 1:
          raise e

        time.sleep(self._retry_wait_time)
        continue

      decoder = BinaryPayloadDecoder.fromRegisters(
        result.registers, byteorder=Endian.Big, wordorder=Endian.Big)
      decoded_value = DATA_TYPE_TO_DECODER_MAP[metric.data_type](decoder)
      return decoded_value * metric.scaling_factor
