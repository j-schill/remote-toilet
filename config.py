import os

from attr import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Credentials:
    username: str = os.getenv("WHISKER_USERNAME", "Your username")
    password: str = os.getenv("WHISKER_PASSWORD", "Your password")


@dataclass
class Config:
    credentials: Credentials = Credentials()
