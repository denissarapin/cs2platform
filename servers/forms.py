from django import forms
from django.core.validators import RegexValidator

MODE_CHOICES = [
    ("dm", "DM"),
    ("1v1", "1 vs 1"),
    ("retake", "Retake"),
    ("hsdm", "HSDM"),
    ("pistoldm", "Pistol DM"),
    ("surf", "Surf"),
    ("bhop", "Bhop"),
    ("kz", "KZ"),
    ("execute", "Execute"),
    ("multicfg", "Multicfg"),
]

MAP_CHOICES = [
    ("de_mirage", "Mirage"),
    ("de_dust2", "Dust2"),
    ("de_ancient", "Ancient"),
    ("de_overpass", "Overpass"),
    ("de_train", "Train"),
    ("de_inferno", "Inferno"),
    ("de_nuke", "Nuke"),
]

_ip_port_validator = RegexValidator(
    regex=r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$",
    message="Enter the address in format 127.0.0.1:27015",
)

class ModeSelectForm(forms.Form):
    mode = forms.ChoiceField(choices=MODE_CHOICES, required=True, label="Mode")

    def clean_mode(self):
        v = self.cleaned_data["mode"]
        allowed = {c for c, _ in MODE_CHOICES}
        if v not in allowed:
            raise forms.ValidationError("Unknown mode")
        return v

class ServerQuickConnectForm(forms.Form):
    server = forms.CharField(
        label="IP:Port",
        max_length=21,
        required=True,
        help_text="Например: 127.0.0.1:27015",
        validators=[_ip_port_validator],
        widget=forms.TextInput(attrs={"placeholder": "127.0.0.1:27015", "class": "form-control"}),
    )

class FilterServersForm(forms.Form):
    map = forms.ChoiceField(choices=[("", "Any map")] + MAP_CHOICES, required=False)
    not_full = forms.BooleanField(label="Only with free slots", required=False)

    def cleaned_filters(self):

        return {
            "map": self.cleaned_data.get("map") or None,
            "not_full": bool(self.cleaned_data.get("not_full")),
        }
