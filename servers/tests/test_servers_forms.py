import pytest
from servers.forms import (
    ModeSelectForm,
    ServerQuickConnectForm,
    FilterServersForm,
    MODE_CHOICES,
)

def test_mode_select_form_valid_choice():
    code = MODE_CHOICES[0][0]
    form = ModeSelectForm(data={"mode": code})
    assert form.is_valid()
    assert form.cleaned_data["mode"] == code

def test_mode_select_form_invalid_choice_uses_default_message():
    form = ModeSelectForm(data={"mode": "unknown"})
    assert not form.is_valid()
    assert "Select a valid choice" in form.errors["mode"][0]

def test_server_quick_connect_form_valid_passes():
    form = ServerQuickConnectForm(data={"server": "127.0.0.1:27015"})
    assert form.is_valid()

@pytest.mark.parametrize("value, expected_msg_part", [
    ("", "This field is required."),       
    ("127.0.0.1", "Enter the address in format"),  
    ("127.0.0.1:abc", "Enter the address in format"),
    ("127.0.0.1:1", "Enter the address in format"), 
])
def test_server_quick_connect_form_invalid_fails(value, expected_msg_part):
    form = ServerQuickConnectForm(data={"server": value})
    assert not form.is_valid()
    assert expected_msg_part in form.errors["server"][0]

def test_filter_servers_form_cleaned_filters_empty():
    form = FilterServersForm(data={})
    assert form.is_valid()
    assert form.cleaned_filters() == {"map": None, "not_full": False}

def test_filter_servers_form_cleaned_filters_with_values():
    form = FilterServersForm(data={"map": "de_mirage", "not_full": "on"})
    assert form.is_valid()
    assert form.cleaned_filters() == {"map": "de_mirage", "not_full": True}

def test_mode_select_form_invalid_choice_custom_message():

    form = ModeSelectForm(data={"mode": "zzz"})
    form.fields["mode"].choices = [("zzz", "Zzz")]
    assert not form.is_valid()
    assert "Unknown mode" in form.errors["mode"][0]