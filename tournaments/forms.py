from django import forms
from .models import Tournament
MAX_TEAM_CHOICES = [(8, "8"), (16, "16"), (32, "32")]
HTML_DT = "%Y-%m-%d %H:%M"

class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = ["name", "description", "start_date", "end_date", "logo", "poster"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_date": forms.DateTimeInput(
                attrs={"class": "form-control", "placeholder": "YYYY-MM-DD HH:MM", "autocomplete": "off", "type": "text"},
                format=HTML_DT
            ),
            "end_date": forms.DateTimeInput(
                attrs={"class": "form-control", "placeholder": "YYYY-MM-DD HH:MM", "autocomplete": "off", "type": "text"},
                format=HTML_DT
            ),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "poster": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }
    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for n in ("start_date", "end_date"):
                self.fields[n].input_formats = [HTML_DT, "%Y-%m-%d %H:%M:%S"]

class TournamentSettingsForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = "__all__"
        widgets = {}

    KEEP_FIELDS = [
        "max_teams", "start_date", "end_date", "registration_open", "status",
        "match_best_of", "best_of", "bo",
        "team_size",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keep_only_fields()
        self._setup_max_teams()
        self._setup_team_size()
        self._setup_datetimes()
        self._setup_registration_open()
        self._setup_best_of()
        self._setup_status()

    def _keep_only_fields(self):
        for name in list(self.fields):
            if name not in self.KEEP_FIELDS:
                self.fields.pop(name)

    def _setup_max_teams(self):
        if "max_teams" not in self.fields:
            return
        base_choices = [8, 16, 32]
        current = int(getattr(self.instance, "max_teams", 16) or 16)
        choices = [(v, str(v)) for v in base_choices]
        if current not in base_choices:
            choices = [(current, str(current))] + choices
        self.fields["max_teams"] = forms.TypedChoiceField(
            choices=choices,
            coerce=int,
            initial=current,
            label="Max teams",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

    def _setup_team_size(self):
        if "team_size" in self.fields:
            self.fields["team_size"].widget = forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            )

    def _setup_datetimes(self):
        for n in ("start_date", "end_date"):
            if n in self.fields:
                self.fields[n].widget = forms.DateTimeInput(
                    attrs={"type": "datetime-local", "class": "form-control"},
                    format=HTML_DT,
                )
                self.fields[n].input_formats = [HTML_DT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    def _setup_registration_open(self):
        if "registration_open" in self.fields:
            self.fields["registration_open"].widget = forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            )

    def _setup_best_of(self):
        bo_name = next((n for n in ("match_best_of", "best_of", "bo") if n in self.fields), None)
        if not bo_name:
            return
        self.fields[bo_name].widget = forms.Select(
            choices=[(1, "BO1"), (3, "BO3")],
            attrs={"class": "form-select"},
        )
        self.fields[bo_name].label = "Match rules (Best of)"

    def _setup_status(self):
        if "status" in self.fields:
            self.fields["status"].widget = forms.Select(attrs={"class": "form-select"})