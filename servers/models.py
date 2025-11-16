from dataclasses import dataclass
from typing import Optional
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models

class BaseServerConfig(models.Model):
    name = models.CharField(max_length=64)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(2), MaxValueValidator(64)])
    mode_code = models.CharField(max_length=16)

    class Meta:
        abstract = True  

    def __str__(self) -> str:  
        return f"{self.name} ({self.mode_code}, {self.capacity})"

ip_port_validator = RegexValidator(
    regex=r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$",
    message="Формат: 127.0.0.1:27015",
)

@dataclass(frozen=True, slots=True)
class ServerInfo:
    num: int
    mode_code: str
    mode_name: str
    map: str
    players: int
    capacity: int
    ip: str
    thumb: Optional[str] = None

    def is_full(self) -> bool:
        return self.players >= self.capacity
