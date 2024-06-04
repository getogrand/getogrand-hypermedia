from django.db import models
from model_utils.models import TimeStampedModel, TimeFramedModel


class Profile(TimeStampedModel):
    full_name = models.CharField()
    email = models.EmailField()

    def __str__(self) -> str:
        return f"{self.full_name} ({self.email})"


class Experience(TimeStampedModel, TimeFramedModel):
    profile = models.ForeignKey(to=Profile, on_delete=models.CASCADE)
    company_name = models.CharField()
    positions = models.JSONField(help_text="array of string")

    def __str__(self) -> str:
        return self.company_name


class Duty(TimeStampedModel, TimeFramedModel):
    experience = models.ForeignKey(to=Experience, on_delete=models.CASCADE)
    title = models.CharField()

    def __str__(self) -> str:
        return self.title


class DutyItem(TimeStampedModel):
    duty = models.ForeignKey(to=Duty, on_delete=models.CASCADE)
    title = models.CharField()

    def __str__(self) -> str:
        return self.title


class DutySubitem(TimeStampedModel):
    duty_item = models.ForeignKey(to=DutyItem, on_delete=models.CASCADE)
    title = models.CharField()

    def __str__(self) -> str:
        return self.title
