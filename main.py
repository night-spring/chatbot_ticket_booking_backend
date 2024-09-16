from bson import ObjectId
from datetime import datetime
import pytz
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query, Request
import smtplib
from email.message import EmailMessage
from typing import List
from database import tickets_collection, earnings_collection, profit_collection, shows_collections, payment_collection
from model import Earnings, Tickets, ResolutionTime, Shows, PaymentDetails, TicketRequest, DialogflowRequest

# from insert import insert_initial_data
# FastAPI app setup
app = FastAPI()

# CORS setup to allow React frontend
# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to actual frontend URL if different
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Earnings Model and Collection
@app.middleware("http")
async def custom_middleware(request, call_next):
    response = await call_next(request)
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


@app.post("/ticket_booking/payment")
async def update_payment(payment_details: PaymentDetails):
    # Check if email already exists to avoid duplicate payments
    existing_payment = await payment_collection.find_one({
        "email": payment_details.email,
    })

    # Simulate payment processing here (add real payment gateway logic)
    # For simplicity, let's assume the payment is successful

    # Insert payment details into the database
    result = await payment_collection.insert_one(payment_details.dict())
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to save payment details")

    # Update ticket count after successful payment
    event_id = ObjectId(payment_details.eventId)
    event = await shows_collections.find_one({"_id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    new_tickets_left = event.get("ticketsLeft", 0) - payment_details.seatCount
    if new_tickets_left < 0:
        raise HTTPException(status_code=400, detail="Not enough tickets left")

    # Update the tickets left in the database
    update_result = await shows_collections.update_one(
        {"_id": event_id},
        {"$set": {"ticketsLeft": new_tickets_left}}
    )

    if update_result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update tickets")

    # Function to send emai
    email_address = "debojit94333@gmail.com"  # Your Gmail
    email_password = "qabi jido ztsf waut"  # App-specific password

    # Create the email body
    msg = EmailMessage()
    msg['Subject'] = f"Ticket Booking Confirmation for {event['title']}"
    msg['From'] = email_address
    msg['To'] = payment_details.email
    msg.set_content(
        f"""\
                Dear Customer,

                Thank you for booking tickets for the show: {event['title']}.

                Here are the details of your booking:
                - Show Name: {event['title']}
                - Date: {event['date']}
                - Time: {event['time']}
                - Ticket Booked: {payment_details.seatCount}

                Your ticket has been successfully booked, and we look forward to seeing you at the event.

                If you have any questions, feel free to contact us.
                - Link : "A"

                Best regards,
                Quicktix
                """
    )

    try:
        # Send email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_address, email_password)
            smtp.send_message(msg)
        return {
            "message": "Payment successful and tickets updated",
            "id": str(result.inserted_id),
            "ticketsLeft": new_tickets_left,
            "email_status": "Email successfully sent"
        }
    except Exception as e:
        return f"Failed to send email: {str(e)}"


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


# chatbot


def handle_hindi(body):
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        "मैं आपकी किस प्रकार मदद कर सकता हूँ?"
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "टिकट"},
                                    {"text": "भाषा"}
                                ]
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_hindi_ticket(body):
    response = {
        "fulfillmentMessages": [
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "event": {
                                    "name": "ReserveTicketsHindi",
                                    "parameters": {
                                        "ticket_type": "प्रवेश"
                                    }
                                },
                                "title": "प्रवेश",
                                "subtitle": "संग्रहालय तक प्रवेश\n₹70",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "event": {
                                    "parameters": {
                                        "ticket_type": "अनमोल धरोहर"
                                    },
                                    "name": "ReserveTicketsHindi"
                                },
                                "title": "अनमोल धरोहर",
                                "subtitle": "ऐतिहासिक कलाकृतियों की प्रदर्शनी\n₹100",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "subtitle": "विभिन्न युगों की कला का विकास\n₹120",
                                "title": "युगों के माध्यम से कला",
                                "event": {
                                    "name": "ReserveTicketsHindi",
                                    "parameters": {
                                        "ticket_type": "युगों के माध्यम से कला"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "subtitle": "अतीत की छुपी कहानियों को जानें\n₹150",
                                "type": "list",
                                "title": "अनकही कहानियाँ",
                                "event": {
                                    "name": "ReserveTicketsHindi",
                                    "parameters": {
                                        "ticket_type": "अनकही कहानियाँ"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "subtitle": "आधुनिकता का प्रदर्शन\n₹100",
                                "event": {
                                    "name": "ReserveTicketsHindi",
                                    "parameters": {
                                        "ticket_type": "आधुनिक माहिर"
                                    }
                                },
                                "type": "list",
                                "title": "आधुनिक माहिर"
                            }
                        ]
                    ]
                }

            }
        ]
    }
    return response


def handle_marathi(body):
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        "मी तुम्हाला कसे मदत करू शकतो?"
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "तिकिटे"},
                                    {"text": "भाषा"}
                                ]
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_marathi_ticket(body):
    response = {
        "fulfillmentMessages": [
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "event": {
                                    "name": "ReserveTicketsMarathi",
                                    "parameters": {
                                        "ticket_type": "प्रवेश"
                                    }
                                },
                                "title": "प्रवेश",
                                "subtitle": "संग्रहालयात प्रवेश\n₹70",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "event": {
                                    "name": "ReserveTicketsMarathi",
                                    "parameters": {
                                        "ticket_type": "अमर खजिना"
                                    }
                                },
                                "title": "अमर खजिना",
                                "subtitle": "ऐतिहासिक कलाकृतींचे प्रदर्शन\n₹100",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "युगानुयुगे कला",
                                "subtitle": "विविध कालखंडातील कलेचा विकास\n₹120",
                                "event": {
                                    "name": "ReserveTicketsMarathi",
                                    "parameters": {
                                        "ticket_type": "युगानुयुगे कला"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "अकथित कथा",
                                "subtitle": "भूतकाळातील लपलेल्या कथा उलगडा करा\n₹150",
                                "event": {
                                    "name": "ReserveTicketsMarathi",
                                    "parameters": {
                                        "ticket_type": "अकथित कथा"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "आधुनिक माहेर",
                                "subtitle": "आधुनिकतेचे प्रदर्शन\n₹100",
                                "event": {
                                    "name": "ReserveTicketsMarathi",
                                    "parameters": {
                                        "ticket_type": "आधुनिक माहेर"
                                    }
                                }
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_bengali(body):
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        "কিভাবে আমি আপনাকে সাহায্য করতে পারি?"
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "টিকেট"},
                                    {"text": "ভাষা"}
                                ]
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_bengali_ticket(body):
    response = {
        "fulfillmentMessages": [
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "event": {
                                    "name": "ReserveTicketsBengali",
                                    "parameters": {
                                        "ticket_type": "প্রবেশ"
                                    }
                                },
                                "title": "প্রবেশ",
                                "subtitle": "জাদুঘরে প্রবেশাধিকার\n₹70",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "event": {
                                    "name": "ReserveTicketsBengali",
                                    "parameters": {
                                        "ticket_type": "চিরন্তন ধন"
                                    }
                                },
                                "title": "চিরন্তন ধন",
                                "subtitle": "ঐতিহাসিক নিদর্শনের প্রদর্শনী\n₹100",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "যুগে যুগে শিল্পকলা",
                                "subtitle": "বিভিন্ন যুগের শিল্পকলার বিকাশ\n₹120",
                                "event": {
                                    "name": "ReserveTicketsBengali",
                                    "parameters": {
                                        "ticket_type": "যুগে যুগে শিল্পকলা"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "অজানা গল্পগুলি",
                                "subtitle": "অতীতের গোপন গল্প আবিষ্কার করুন\n₹150",
                                "event": {
                                    "name": "ReserveTicketsBengali",
                                    "parameters": {
                                        "ticket_type": "অজানা গল্পগুলি"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "আধুনিক মায়েস্ত্রো",
                                "subtitle": "আধুনিকতার প্রদর্শনী\n₹100",
                                "event": {
                                    "name": "ReserveTicketsBengali",
                                    "parameters": {
                                        "ticket_type": "আধুনিক মায়েস্ত্রো"
                                    }
                                }
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_tamil(body):
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        "நான் உங்களுக்கு எப்படி உதவ முடியும்?"
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "டிக்கெட்டுகள்"},
                                    {"text": "மொழி"}
                                ]
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_tamil_ticket(body):
    response = {
        "fulfillmentMessages": [
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "event": {
                                    "name": "ReserveTicketsTamil",
                                    "parameters": {
                                        "ticket_type": "நுழைவு"
                                    }
                                },
                                "title": "நுழைவு",
                                "subtitle": "அருங்காட்சியகத்தில் நுழைவு\n₹70",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "event": {
                                    "name": "ReserveTicketsTamil",
                                    "parameters": {
                                        "ticket_type": "நிறம்கொடையில்லா நிதிகள்"
                                    }
                                },
                                "title": "நிறம்கொடையில்லா நிதிகள்",
                                "subtitle": "வரலாற்று பொருட்களின் கண்காட்சி\n₹100",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "காலங்களின் வழியாகக் கலை",
                                "subtitle": "பல்வேறு காலக்கட்டங்களில் கலை வளர்ச்சி\n₹120",
                                "event": {
                                    "name": "ReserveTicketsTamil",
                                    "parameters": {
                                        "ticket_type": "காலங்களின் வழியாகக் கலை"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "சொல்லப்படாத கதைகள்",
                                "subtitle": "கடந்த காலத்தின் மறைந்த கதைகளை கண்டறியுங்கள்\n₹150",
                                "event": {
                                    "name": "ReserveTicketsTamil",
                                    "parameters": {
                                        "ticket_type": "சொல்லப்படாத கதைகள்"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "நவீன இசைஞர்",
                                "subtitle": "நவீனத்தை அறிமுகப்படுத்துகிறது\n₹100",
                                "event": {
                                    "name": "ReserveTicketsTamil",
                                    "parameters": {
                                        "ticket_type": "நவீன இசைஞர்"
                                    }
                                }
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_telugu_ticket(body):
    response = {
        "fulfillmentMessages": [
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "event": {
                                    "name": "ReserveTicketsTelugu",
                                    "parameters": {
                                        "ticket_type": "ప్రవేశం"
                                    }
                                },
                                "title": "ప్రవేశం",
                                "subtitle": "సంగ్రహాలయంలోకి ప్రవేశం\n₹70",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "event": {
                                    "name": "ReserveTicketsTelugu",
                                    "parameters": {
                                        "ticket_type": "శాశ్వత ఖజానా"
                                    }
                                },
                                "title": "శాశ్వత ఖజానా",
                                "subtitle": "చారిత్రక కళాఖండాల ప్రదర్శన\n₹100",
                                "type": "list"
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "యుగాల ద్వారా కళ",
                                "subtitle": "వివిధ యుగాలలో కళ యొక్క పరిణామం\n₹120",
                                "event": {
                                    "name": "ReserveTicketsTelugu",
                                    "parameters": {
                                        "ticket_type": "యుగాల ద్వారా కళ"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "చెప్పని కథలు",
                                "subtitle": "గతంలోని దాచిన కథలను వెలికితీయండి\n₹150",
                                "event": {
                                    "name": "ReserveTicketsTelugu",
                                    "parameters": {
                                        "ticket_type": "చెప్పని కథలు"
                                    }
                                }
                            },
                            {
                                "type": "divider"
                            },
                            {
                                "type": "list",
                                "title": "ఆధునిక మాస్ట్రో",
                                "subtitle": "ఆధునికతను ప్రదర్శిస్తోంది\n₹100",
                                "event": {
                                    "name": "ReserveTicketsTelugu",
                                    "parameters": {
                                        "ticket_type": "ఆధునిక మాస్ట్రో"
                                    }
                                }
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_telugu(body):
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        "నేను మీకు ఎలా సహాయపడగలను?"
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "టిక్కెట్లు"},
                                    {"text": "భాష"}
                                ]
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_reserve_tickets(body):
    parameters = body.get("queryResult", {}).get("parameters", {})
    ticket = int(parameters.get("ticket", 0))  # Convert to int if necessary
    email = parameters.get("email")
    ticket_type = parameters.get("ticket_type")
    ticket_cost = 70
    total_cost = ticket * ticket_cost
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        f"Your total is ₹{total_cost}, \nthe tickets will be mailed to you at {email}.\nProceed for payment:"
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "options": [
                                    {
                                        "image": {
                                            "src": {
                                                "rawUrl": "https://imgur.com/fp0VcNM"
                                            }
                                        },
                                        "text": "Google Pay",
                                        "link": "https://example.com/googlepay"
                                    },
                                    {
                                        "link": "https://example.com/phonepe.com",
                                        "image": {
                                            "src": {
                                                "rawUrl": "https://s3.amazonaws.com/shecodesio-production/uploads/files/000/143/327/original/Create_Account.jpeg?1726258586"
                                            }
                                        },
                                        "text": "PhonePe"
                                    },
                                    {
                                        "link": "https://example.com/credit-card-payment",
                                        "text": "Credit Card",
                                        "image": {
                                            "src": {
                                                "rawUrl": " https://s3.amazonaws.com/shecodesio-production/uploads/files/000/143/328/original/Credit_cards_vector_icon.jpeg?1726258598"
                                            }
                                        }
                                    }
                                ],
                                "type": "chips"
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


def handle_text_tickets(body):
    parameters = body.get("queryResult", {}).get("parameters", {})
    ticket = int(parameters.get("Ticket", 0))
    ticket_cost = 70
    total_cost = ticket * ticket_cost
    payment_link = 'placeholder'
    fulfillment_text = f"Your total is ₹{total_cost}, proceed for payment: \n{payment_link}."
    response = {"fulfillmentText": fulfillment_text}
    return response


def handle_default(body):
    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        "I didn't understand."
                    ]
                }
            },
            {
                "payload": {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": [
                                    {
                                        "text": "Available Tickets"
                                    },
                                    {
                                        "text": "Language"
                                    }
                                ]
                            }
                        ]
                    ]
                }
            }
        ]
    }
    return response


# Map intent names to handler functions
INTENT_HANDLERS = {
    "hindi": handle_hindi,
    "marathi": handle_marathi,
    "bengali": handle_bengali,
    "tamil": handle_tamil,
    "telugu": handle_telugu,

    "ReserveTickets": handle_reserve_tickets,
    "Text_tickets": handle_text_tickets,

    "LangHindi": handle_hindi_ticket,
    "LangMarathi": handle_marathi_ticket,
    "LangBengali": handle_bengali_ticket,
    "LangTamil": handle_tamil_ticket,
    "LangTelugu": handle_telugu_ticket,
}


@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
        intent_name = body.get("queryResult", {}).get("intent", {}).get("displayName")

        handler = INTENT_HANDLERS.get(intent_name, handle_default)
        response = handler(body)

        return response
    except Exception as e:
        # Log and return the error message
        print(f"Error: {e}")
        return {
            "fulfillmentText": f"Webhook error: {str(e)}"
        }
