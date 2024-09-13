from bson import ObjectId
from datetime import datetime
import pytz
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query
from typing import List
from database import tickets_collection, earnings_collection, profit_collection, shows_collections, payment_collection
from model import Earnings, Tickets, ResolutionTime, Shows, TicketUpdate, PaymentDetails, TicketRequest
#from insert import insert_initial_data
# FastAPI app setup
app = FastAPI()

# CORS setup to allow React frontend
# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Change to actual frontend URL if different
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Earnings Model and Collection
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    await init_db() # already in the previous snippet

    response = await call_next(request)

    await Tortoise.close_connections() # Now also close the session after each call

    return response

@app.get("/")
def home():
    return {"message": "Hello World"}

# Fetch earnings data dynamically from MongoDB
@app.get("/earning", response_model=List[Earnings])
async def get_earning():
    try:
        earnings = await earnings_collection.find().to_list(100)
        if not earnings:
            raise HTTPException(status_code=404, detail="No earnings data found.")
        # Ensure we remove '_id' from each document and match the data model structure
        for earning in earnings:
            earning.pop("_id", None)  # Remove MongoDB _id field if present
        return earnings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Fetch ticket analytics data from MongoDB
@app.get("/tickets-analytics", response_model=List[Tickets])
async def get_ticket_analytics():
    try:
        tickets = await tickets_collection.find().to_list(100)
        if not tickets:
            raise HTTPException(status_code=404, detail="No ticket analytics found.")
        return tickets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Fetch resolution time data from MongoDB
@app.get("/profit", response_model=List[ResolutionTime])
async def get_profits():
    try:
        profit = await profit_collection.find().to_list(100)
        if not profit:
            raise HTTPException(status_code=404, detail="No resolution time data found.")
        return profit
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


# Fetch show name and time data from MongoDB
@app.get("/shows", response_model=List[Shows])
async def get_shows():
    try:
        shows = await shows_collections.find().to_list(100)
        if not shows:
            raise HTTPException(status_code=404, detail="No resolution time data found.")
        return shows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.get("/ticket_booking", response_model=dict)
async def get_event(event_id: str = Query(..., alias="event_id")):
    event = await shows_collections.find_one({"_id": ObjectId(event_id)})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "ticketsLeft": int(event.get("ticketsLeft", 0)),
    }


# The existing POST endpoint for updating ticket bookings
@app.post("/ticket_booking/update")
async def update_ticket_booking(ticket_update: TicketUpdate):
    event_id = ObjectId(ticket_update.eventId)
    event = await shows_collections.find_one({"_id": event_id})
    new_tickets_left = event.get("ticketsLeft", 0) - ticket_update.ticketsBought
    if new_tickets_left < 0:
        raise HTTPException(status_code=400, detail="Not enough tickets left")
    result = await shows_collections.update_one(
        {"_id": event_id},
        {"$set": {"ticketsLeft": new_tickets_left}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update tickets left")
    return {"success": True, "ticketsLeft": new_tickets_left}  # Return updated ticketsLeft

@app.post("/ticket_booking/payment")
async def update_payment(payment_details: PaymentDetails):
    # Check if email or phone number already exists
    existing_payment = await payment_collection.find_one({
        "email": payment_details.email,
        "phone": payment_details.phone
    })

    if existing_payment:
        raise HTTPException(status_code=400, detail="Payment details already exist")

    # Insert payment details into the database
    result = await payment_collection.insert_one(payment_details.dict())

    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to save payment details")

    return {"message": "Payment details saved successfully", "id": str(result.inserted_id)}
@app.post("/reserve_tickets/")
async def reserve_tickets(response: TicketRequest):
    time_str = response.queryResult["parameters"]["time"]
    num_tickets = response.queryResult["parameters"]["ticketLeft"]

    try:
        show_time = datetime.strptime(time_str, "%I %p").replace(tzinfo=pytz.UTC)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format provided.")

    show = shows_collections.find_one({"show_time": show_time})

    if not show:
        raise HTTPException(status_code=404, detail="No show found at the specified time.")

    if show["available_seats"] < num_tickets:
        raise HTTPException(status_code=400, detail="Not enough tickets available.")

    shows_collections.update_one(
        {"_id": show["_id"]},
        {"$inc": {"available_seats": -num_tickets}}
    )

    return {"fulfillmentText": f"Your {num_tickets} tickets are reserved for the {time_str} show."}

# Call the data insertion function on startup
'''@app.on_event("startup")
async def startup_event():
    await insert_initial_data()'''

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
