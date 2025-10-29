from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        help_texts = {f: "" for f in fields}  # убираем help_text в мета

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # на всякий случай глушим ещё раз
        for f in ("username", "password1", "password2"):
            self.fields[f].help_text = ""

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "avatar", "steam_id"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Введите имя пользователя"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Введите email"}),
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
            "steam_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Введите Steam ID"}),
        }
        labels = {
            "username": "Имя пользователя",
            "email": "Email",
            "avatar": "Аватар",
            "steam_id": "Steam ID",
        }
        help_texts = {
            "username": "",
            "email": "",
            "avatar": "",
            "steam_id": "",
        }

class SteamLookupForm(forms.Form):
    steam_id = forms.CharField(
        label="SteamID64",
        required=False,
        max_length=64,
        widget=forms.TextInput(attrs={
            "placeholder": "7656119…",
            "class": "form-control",
            "inputmode": "numeric",
            "autocomplete": "off",
        }),
        help_text="Можно ввести SteamID64 вручную (приоритетнее подключённого Steam).",
    )

    def clean_steam_id(self):
        v = (self.cleaned_data.get("steam_id") or "").strip()
        # Жёстко не валидируем: резолвинг делаем во view через Steam API.
        if " " in v:
            raise forms.ValidationError("Ввод без пробелов. Вставь SteamID64, ссылку или alias.")
        return v