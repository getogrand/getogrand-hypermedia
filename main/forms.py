from django import forms

from .models import Profile


class ProfileForm(forms.Form):
    expanded_experience_ids = forms.TypedMultipleChoiceField(
        coerce=int,
        widget=forms.SelectMultiple(attrs={"class": "hidden", "hx-swap-oob": "true"}),
        required=False,
    )

    def __init__(self, profile: Profile, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expanded_experience_ids"].choices = [
            (experience.id, experience.company_name)
            for experience in profile.experience_set.all()
        ]
