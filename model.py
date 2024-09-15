from bson import ObjectId
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional, Any, List


class Earnings(BaseModel):
    productSales: int
    subscriptionFees: int
    serviceCharges: int
    miscellaneous: int


# Tickets Model and Collection
class Tickets(BaseModel):
    name: str
    tickets: int
    resolutionTime: int


# Resolution Time Model and Collection
class ResolutionTime(BaseModel):
    name: str
    earning: int
    cost: int
    profit: int


class Shows(BaseModel):
    image: str
    title: str
    date: str
    time: str
    location: str
    price: str
    ticketsLeft: int
    id: str


class PaymentDetails(BaseModel):
    eventId: str
    selectedSeats: List[int]
    seatCount: int
    email: EmailStr
    amount: float


class TicketRequest(BaseModel):
    queryResult: dict


# Define the structure of the Dialogflow request
class QueryResult(BaseModel):
    parameters: Dict[str, Any]
    intent: Dict[str, str]

class DialogflowRequest(BaseModel):
    queryResult: QueryResult
