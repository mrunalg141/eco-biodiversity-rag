import os
import time
import io

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader

from app.rag import embedder, index_pdf, clear_collection
from app.llm import (
    get_ai_reply,
    get_environmental_followup,
    get_environmental_recommendation
)
from app.database import (
    init_db,
    save_message,
    get_all_messages,
    init_documents_table,
    save_document,
    clear_messages
)


app = FastAPI(title="StudyMate")

# Stores temporary environmental information during a conversation
environmental_state = {}


# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# Initialize database
init_db()
init_documents_table()

# Create uploads directory
os.makedirs("./uploads", exist_ok=True)



class ChatMessage(BaseModel):
    message: str


class EnvironmentalInput(BaseModel):
    soil_organic_carbon: float
    rainfall: str
    land_use: str



@app.get("/test-embed")
def test_embed():
    texts = [
        "This is a test sentence about machine learning."
    ] * 8

    t0 = time.time()

    embeddings = list(embedder.embed(texts))

    elapsed = time.time() - t0

    return {
        "elapsed_seconds": elapsed
    }



@app.get("/")
def read_root(request: Request):
    messages = get_all_messages()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "messages": messages
        }
    )




@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    pdf_bytes = await file.read()

    
    save_path = f"./uploads/{file.filename}"

    with open(save_path, "wb") as f:
        f.write(pdf_bytes)

    
    reader = PdfReader(io.BytesIO(pdf_bytes))

    extracted_text = ""

    for page in reader.pages:
        extracted_text += page.extract_text() or ""

    save_document(
        file.filename,
        extracted_text
    )

   
    num_chunks = index_pdf(
        save_path,
        doc_id=file.filename
    )

    return {
        "message": f"'{file.filename}' uploaded successfully.",
        "chunks": num_chunks
    }




@app.post("/environment/recommend")
def environmental_recommend(data: EnvironmentalInput):

    environmental_data = {
        "soil_organic_carbon": f"{data.soil_organic_carbon}%",
        "rainfall": data.rainfall,
        "land_use": data.land_use
    }

    result = get_environmental_recommendation(
        environmental_data
    )

    return {
        "recommendation": result.recommendation,
        "reasoning": result.reasoning,
        "metrics_impacted": result.metrics_impacted,
        "time_horizon": result.time_horizon,
        "confidence": result.confidence,
        "sources": result.sources
    }




@app.post("/chat")
def chat(chat_message: ChatMessage):

    user_message = chat_message.message
    user_id = "default"

  

    if "biodiversity" in user_message.lower():

        environmental_state[user_id] = {
            "soil_organic_carbon": None,
            "rainfall": None,
            "land_use": None
        }

        bot_reply = (
            "I can assess the biodiversity risk using your environmental conditions. "
            "Please provide these 3 details:\n"
            "1. Soil organic carbon %\n"
            "2. Rainfall pattern (low / medium / high)\n"
            "3. Land use / crop type"
        )

    

    elif user_id in environmental_state:

        parts = [
            p.strip()
            for p in user_message.split(",")
        ]

        # Not enough information
        if len(parts) < 3:

            bot_reply = (
                "Please provide all 3 details separated by commas.\n"
                "Example: 0.3%, low rainfall, monoculture wheat"
            )

        
        else:

            environmental_data = {
                "soil_organic_carbon": parts[0],
                "rainfall": parts[1],
                "land_use": parts[2]
            }

            result = get_environmental_recommendation(
                environmental_data
            )

            bot_reply = (
             f"Recommendation: {result.recommendation}\n\n"
             f"Reasoning: {result.reasoning}\n\n"
             f"Metrics impacted: {', '.join(result.metrics_impacted)}\n\n"
             f"Time horizon: {result.time_horizon}"
           )

            # Clear temporary environmental state
            del environmental_state[user_id]

    

    else:

        bot_reply = get_ai_reply(
            user_message
        )

    
    save_message(
        user_message,
        bot_reply
    )

    return {
        "reply": bot_reply
    }




@app.post("/clear")
def clear_chat():

    clear_messages()
    clear_collection()


    # Also clear environmental conversation state
    environmental_state.clear()

    return {
        "message": "Chat history and uploaded documents cleared."
    }