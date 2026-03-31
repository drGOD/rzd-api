from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    language: str = 'ru'
    timeout: float = 5.0
    debug: bool = False
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
