# teams/forms.py
from django import forms
from .models import Team

class TeamCreateForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ('name', 'tag', 'logo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.update({'class': 'form-control'})

class TeamUpdateForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ('name', 'tag', 'logo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.update({'class': 'form-control'})
