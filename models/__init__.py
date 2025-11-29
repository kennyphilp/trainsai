"""
Response models for UK National Rail API Client.

This package contains Pydantic models for API responses.
"""

from .train_departure import TrainDeparture
from .departure_board_response import DepartureBoardResponse
from .departure_board_error import DepartureBoardError
from .detailed_train_departure import DetailedTrainDeparture
from .detailed_departures_response import DetailedDeparturesResponse
from .detailed_departures_error import DetailedDeparturesError
from .affected_operator import AffectedOperator
from .incident import Incident
from .station_messages_response import StationMessagesResponse
from .station_messages_error import StationMessagesError
from .service_location import ServiceLocation
from .service_details_response import ServiceDetailsResponse
from .service_details_error import ServiceDetailsError

__all__ = [
    'TrainDeparture',
    'DepartureBoardResponse',
    'DepartureBoardError',
    'DetailedTrainDeparture',
    'DetailedDeparturesResponse',
    'DetailedDeparturesError',
    'AffectedOperator',
    'Incident',
    'StationMessagesResponse',
    'StationMessagesError',
    'ServiceLocation',
    'ServiceDetailsResponse',
    'ServiceDetailsError',
]
