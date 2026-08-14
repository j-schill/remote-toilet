import os

from attr import dataclass


@dataclass
class Credentials:
    username: str = os.getenv("WHISKER_USERNAME", "Your username")
    password: str = os.getenv("WHISKER_PASSWORD", "Your password")


@dataclass
class Config:
    credentials: Credentials = Credentials()
