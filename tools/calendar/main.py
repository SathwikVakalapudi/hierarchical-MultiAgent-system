from fastapi import FastAPI
from tools.calendar.oauth import router

app = FastAPI()
app.include_router(router)
