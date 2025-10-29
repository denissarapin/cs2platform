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
            # ВАЖНО: обычный TextInput, чтобы повесить JS-календарь
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
    """
    Форма настроек: берём __all__ и оставляем только нужные, которые реально есть в модели.
    Никаких Unknown field ошибок.
    """
    class Meta:
        model = Tournament
        fields = "__all__"   # потом выкинем лишние в __init__
        widgets = {}         # виджеты назначим динамически в __init__

    # Поля, которые хотим показывать, если они существуют в модели
    KEEP_FIELDS = [
        "max_teams", "start_date", "end_date", "registration_open", "status",
        # возможные варианты поля «best of»
        "match_best_of", "best_of", "bo",
        # если у тебя есть team_size — отрендерится; если нет — его тут просто не будет
        "team_size",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1) Оставляем только нужные поля
        for name in list(self.fields):
            if name not in self.KEEP_FIELDS:
                self.fields.pop(name)

        # 2) max_teams — делаем Select с 8/16/32
        if "max_teams" in self.fields:
            base_choices = [8, 16, 32]
            current = int(getattr(self.instance, "max_teams", 16) or 16)

            # если в базе сохранено не 8/16/32 — добавим текущий первым пунктом,
            # чтобы форма корректно отрисовалась и дала сохранить
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

        # 3) Числовые поля
        if "team_size" in self.fields:
            self.fields["team_size"].widget = forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            )

        # 4) Даты — html5 datetime-local + несколько форматов парсинга
        for n in ("start_date", "end_date"):
            if n in self.fields:
                self.fields[n].widget = forms.DateTimeInput(
                    attrs={"type": "datetime-local", "class": "form-control"},
                    format=HTML_DT,
                )
                self.fields[n].input_formats = [HTML_DT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

        # 5) Чекбокс регистрации
        if "registration_open" in self.fields:
            self.fields["registration_open"].widget = forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            )

        # 6) Приведём «best of» к Select (если поле существует под любым из имён)
        bo_name = next((n for n in ("match_best_of", "best_of", "bo") if n in self.fields), None)
        if bo_name:
            self.fields[bo_name].widget = forms.Select(
                choices=[(1, "BO1"), (3, "BO3")],
                attrs={"class": "form-select"},
            )
            self.fields[bo_name].label = "Match rules (Best of)"

        # 7) Статус — тоже нормализуем на красивый select, если поле присутствует
        if "status" in self.fields:
            self.fields["status"].widget = forms.Select(attrs={"class": "form-select"})