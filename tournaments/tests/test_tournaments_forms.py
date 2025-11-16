import pytest
from django import forms
from django.utils import timezone
from tournaments.forms import TournamentForm, TournamentSettingsForm, HTML_DT
from tournaments.models import Tournament

def _has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())

@pytest.mark.django_db
def test_tournament_form_datetime_widgets_and_formats():
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    form = TournamentForm(instance=t)

    for n in ("start_date", "end_date"):
        field = form.fields[n]
        assert isinstance(field.widget, forms.DateTimeInput)
        assert HTML_DT in field.input_formats
        assert getattr(field.widget, "input_type", None) == "text"
        assert field.widget.attrs.get("placeholder") == "YYYY-MM-DD HH:MM"
        assert field.widget.attrs.get("autocomplete") == "off"

@pytest.mark.django_db
def test_settings_form_max_teams_injects_current_value_if_custom():
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        max_teams=20,
        registration_open=True,
        status="upcoming",
    )
    form = TournamentSettingsForm(instance=t)

    assert "max_teams" in form.fields
    f = form.fields["max_teams"]
    assert isinstance(f, forms.TypedChoiceField)
    assert f.choices[0] == (20, "20")
    assert (8, "8") in f.choices and (16, "16") in f.choices and (32, "32") in f.choices
    assert f.initial == 20
    assert f.coerce is int
    assert isinstance(f.widget, forms.Select)
    assert f.widget.attrs.get("class") == "form-select"


@pytest.mark.django_db
def test_settings_form_setup_team_size_without_model_field():
    t = Tournament.objects.create(name="Cup", start_date=timezone.now(), max_teams=16, status="upcoming", registration_open=True)
    form = TournamentSettingsForm(instance=t)
    form.fields["team_size"] = forms.IntegerField()
    form._setup_team_size()
    w = form.fields["team_size"].widget
    assert isinstance(w, forms.NumberInput)
    assert w.attrs.get("class") == "form-control"
    assert w.attrs.get("min") == 1


@pytest.mark.django_db
@pytest.mark.parametrize("bo_name", ["match_best_of", "best_of", "bo"])
def test_settings_form_setup_best_of_without_model_field(bo_name):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now(), max_teams=16, status="upcoming", registration_open=True)
    form = TournamentSettingsForm(instance=t)
    form.fields[bo_name] = forms.IntegerField()
    form._setup_best_of()
    fld = form.fields[bo_name]
    assert isinstance(fld.widget, forms.Select)
    assert (1, "BO1") in fld.widget.choices
    assert (3, "BO3") in fld.widget.choices
    assert fld.label == "Match rules (Best of)"


@pytest.mark.django_db
def test_settings_form_max_teams_injects_current_value_not_in_base():
    t = Tournament.objects.create(name="Cup", start_date=timezone.now(), max_teams=20, status="upcoming", registration_open=True)
    form = TournamentSettingsForm(instance=t)
    f = form.fields["max_teams"]
    assert f.choices[0] == (20, "20")

@pytest.mark.django_db
def test_settings_form_setup_max_teams_skips_when_absent():
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
    )
    form = TournamentSettingsForm(instance=t)
    if "max_teams" in form.fields:
        form.fields.pop("max_teams")
    form._setup_max_teams()
    assert "max_teams" not in form.fields


@pytest.mark.django_db
def test_settings_form_setup_datetimes_skips_when_fields_absent():
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    form = TournamentSettingsForm(instance=t)
    form.fields.pop("start_date", None)
    form.fields.pop("end_date", None)
    form._setup_datetimes()
    assert "start_date" not in form.fields and "end_date" not in form.fields

@pytest.mark.django_db
def test_settings_form_setup_best_of_skips_when_absent():
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    form = TournamentSettingsForm(instance=t)
    for n in ("match_best_of", "best_of", "bo"):
        form.fields.pop(n, None)
    form._setup_best_of()
    for n in ("match_best_of", "best_of", "bo"):
        assert n not in form.fields

@pytest.mark.django_db
def test_settings_form_setup_status_skips_when_absent():
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    form = TournamentSettingsForm(instance=t)
    form.fields.pop("status", None)
    form._setup_status() 
    assert "status" not in form.fields

@pytest.mark.django_db
def test_settings_form_registration_open_skips_when_absent(monkeypatch):
    keep_wo_reg = [f for f in TournamentSettingsForm.KEEP_FIELDS if f != "registration_open"]
    monkeypatch.setattr(TournamentSettingsForm, "KEEP_FIELDS", keep_wo_reg, raising=False)
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    form = TournamentSettingsForm(instance=t)
    assert "registration_open" not in form.fields