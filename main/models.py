from django.db import models
from model_utils.models import TimeStampedModel


class Profile(TimeStampedModel):
    full_name = models.CharField()
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.email})"


class DateFramedModel(models.Model):
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True


class Experience(TimeStampedModel, DateFramedModel):
    profile = models.ForeignKey(to=Profile, on_delete=models.CASCADE)
    story = models.TextField()
    company_name = models.CharField()
    positions: models.JSONField[list[str]] = models.JSONField(
        help_text="array of string"
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.profile.save()

    def __str__(self) -> str:
        return self.company_name


class Duty(TimeStampedModel, DateFramedModel):
    experience = models.ForeignKey(to=Experience, on_delete=models.CASCADE)
    title = models.CharField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.experience.save()

    def __str__(self) -> str:
        return self.title


class DutyItem(TimeStampedModel):
    duty = models.ForeignKey(to=Duty, on_delete=models.CASCADE)
    title = models.CharField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.duty.save()

    def __str__(self) -> str:
        return self.title


class DutySubitem(TimeStampedModel):
    duty_item = models.ForeignKey(to=DutyItem, on_delete=models.CASCADE)
    title = models.CharField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.duty_item.save()

    def __str__(self) -> str:
        return self.title
