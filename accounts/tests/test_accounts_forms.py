import pytest
from django.core.exceptions import ValidationError
from accounts.forms import SignUpForm, SteamLookupForm

def test_signup_form_help_texts_are_cleared_on_init():
    form = SignUpForm()
    for f in ("username", "password1", "password2"):
        assert form.fields[f].help_text == ""

def test_steamlookup_clean_returns_stripped_value_without_spaces():
    form = SteamLookupForm(data={"steam_id": "coolalias"})
    assert form.is_valid() is True
    assert form.cleaned_data["steam_id"] == "coolalias"

def test_steamlookup_clean_allows_empty_value():
    form = SteamLookupForm(data={"steam_id": ""})
    assert form.is_valid() is True
    assert form.cleaned_data["steam_id"] == ""

def test_steamlookup_clean_raises_on_spaces_inside():
    form = SteamLookupForm(data={"steam_id": "7656119 123"})
    assert form.is_valid() is False
    assert "steam_id" in form.errors
    assert any("No spaces allowed. Enter SteamID64, link, or alias" in e for e in form.errors["steam_id"])
