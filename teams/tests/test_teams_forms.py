import pytest
from teams.forms import TeamUpdateForm
pytestmark = pytest.mark.django_db


def test_team_update_form_sets_form_control_class_on_all_fields():
    form = TeamUpdateForm()
    assert {"name", "tag", "logo"}.issubset(set(form.fields.keys()))
    for f in form.fields.values():
        assert f.widget.attrs.get("class") == "form-control"


def test_team_update_form_with_instance_sets_classes(team):
    form = TeamUpdateForm(instance=team)
    for f in form.fields.values():
        assert f.widget.attrs.get("class") == "form-control"
