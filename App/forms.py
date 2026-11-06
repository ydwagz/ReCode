import json
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import slugify

from .models import Comment, Profile, Team, utc_today

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.help_text = ""
        self.fields["email"].help_text = "Optional."
        self.fields["password2"].label = "Confirm password"

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already in use.")
        return email


class ProfileForm(forms.ModelForm):
    """Name and bio only — never blocked by anything else on the account."""

    class Meta:
        model = Profile
        fields = ("display_name", "bio")
        widgets = {"bio": forms.Textarea(attrs={"rows": 3, "maxlength": 200})}
        labels = {"display_name": "Display name"}


class EmailForm(forms.Form):
    email = forms.EmailField(required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = user.email

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("That email is already in use.")
        return email

    def save(self):
        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=["email"])
        return self.user


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("default_language", "notify_daily", "notify_team", "notify_streak", "public_profile", "show_on_leaderboard")
        labels = {
            "notify_daily": "New daily challenge",
            "notify_team": "Team activity",
            "notify_streak": "Streak at risk",
            "public_profile": "Public profile",
            "show_on_leaderboard": "Show me on public leaderboards",
        }


class WebhookForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("webhook_url",)
        labels = {"webhook_url": "Webhook URL (POSTed when you solve a challenge)"}


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ("name", "description")

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not slugify(name):
            raise forms.ValidationError("Use at least one letter or number.")
        return name


class CommentForm(forms.ModelForm):
    parent = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Share an idea, ask a question… (no spoilers before the deadline!)"})}
        labels = {"body": ""}


class PrivateChallengeForm(forms.Form):
    title = forms.CharField(max_length=100)
    difficulty = forms.ChoiceField(choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")])
    release_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), help_text="Open for 24h from 00:00 UTC")
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}), help_text="Supports `code` and **bold**.")
    function_name = forms.RegexField(regex=r"^[a-z_][a-z0-9_]*$", max_length=60, help_text="snake_case, e.g. sum_list")
    params = forms.RegexField(regex=r"^\s*[a-z_][a-z0-9_]*(\s*,\s*[a-z_][a-z0-9_]*)*\s*$", max_length=200, help_text="e.g. nums, target")
    reference_python = forms.CharField(widget=forms.Textarea(attrs={"rows": 8, "class": "mono"}), label="Reference solution (Python)")
    examples = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "mono"}), help_text='JSON list of argument lists, e.g. [[[1, 2, 3]], [[4]]]')
    hidden = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "mono"}), help_text="Hidden tests, same format")
    hints = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), help_text="One hint per line, easiest first")

    def clean_release_date(self):
        day = self.cleaned_data["release_date"]
        if day < utc_today() or day > utc_today() + timedelta(days=60):
            raise forms.ValidationError("Pick a date between today and 60 days from now.")
        return day

    def _json_args(self, field):
        try:
            data = json.loads(self.cleaned_data[field])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc
        if not isinstance(data, list) or not data or not all(isinstance(a, list) for a in data):
            raise forms.ValidationError("Must be a non-empty list of argument lists.")
        if len(data) > 50:
            raise forms.ValidationError("At most 50 tests.")
        return data

    def clean_examples(self):
        return self._json_args("examples")

    def clean_hidden(self):
        return self._json_args("hidden")

    def clean_hints(self):
        return [line.strip() for line in self.cleaned_data["hints"].splitlines() if line.strip()][:5]


