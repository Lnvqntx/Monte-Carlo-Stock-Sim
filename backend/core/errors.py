"""Custom exceptions for the simulator core."""


class SimulatorError(Exception):
    """Base class for all simulator errors."""


class InvalidTickerError(SimulatorError):
    """The ticker returned no data (unknown, delisted or mistyped)."""


class InsufficientDataError(SimulatorError):
    """Not enough price history to estimate parameters reliably."""


class DataFetchError(SimulatorError):
    """The data provider could not be reached or returned an error."""
