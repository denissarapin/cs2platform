import types
import pytest
from django.core.exceptions import ValidationError
from servers.models import BaseServerConfig, ServerInfo, ip_port_validator

def test_base_server_config_str_uses_fields():
    obj = types.SimpleNamespace(name="Aim DM #1", mode_code="dm", capacity=16)
    s = BaseServerConfig.__str__(obj)
    assert s == "Aim DM #1 (dm, 16)"

def test_server_info_is_full_true_and_false():
    a = ServerInfo(num=1, mode_code="dm", mode_name="DM",
                   map="de_mirage", players=16, capacity=16, ip="127.0.0.1:27015")
    b = ServerInfo(num=2, mode_code="dm", mode_name="DM",
                   map="de_mirage", players=5, capacity=16, ip="127.0.0.1:27016")
    assert a.is_full() is True
    assert b.is_full() is False

def test_ip_port_validator_ok_and_bad():
    ip_port_validator("127.0.0.1:27015")
    with pytest.raises(ValidationError):
        ip_port_validator("127.0.0.1")
