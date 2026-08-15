from app.database import Base, engine
from app import db_models


Base.metadata.create_all(bind=engine)

print("Database tables created")