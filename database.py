from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection setup
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise Exception("MONGODB_URI not found in environment variables.")

client = AsyncIOMotorClient(MONGODB_URI)
database = client["Ticketing"]

# Define collections
tickets_collection = database["tickets"]
earnings_collection = database["earnings"]
profit_collection = database["profit"]
shows_collections = database["shows"]
payment_collection = database["payments"]
