from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        help_texts = {f: "" for f in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter username"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter email"}),
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
            "steam_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter Steam ID"}),
        }
        labels = {
            "username": "Username",
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
        help_text="You can manually enter a SteamID64 (it takes priority over connected Steam)",
    )

    def clean_steam_id(self):
        v = (self.cleaned_data.get("steam_id") or "").strip()
        if " " in v:
            raise forms.ValidationError("No spaces allowed. Enter SteamID64, link, or alias")
        return v