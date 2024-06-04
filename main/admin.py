from django.contrib import admin

from .models import Profile, Experience, Duty, DutyItem, DutySubitem


class DutySubitemInline(admin.StackedInline):
    model = DutySubitem
    show_change_link = True


class DutyItemInline(admin.StackedInline):
    model = DutyItem
    show_change_link = True


class DutyInline(admin.TabularInline):
    model = Duty
    fields = ["title", "start", "end"]
    show_change_link = True


class ExperienceInline(admin.StackedInline):
    model = Experience
    fields = ["company_name", "start", "end", "positions"]
    show_change_link = True


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    inlines = [ExperienceInline]


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ["company_name", "profile"]
    inlines = [DutyInline]


@admin.register(Duty)
class DutyAdmin(admin.ModelAdmin):
    list_display = ["title", "experience"]
    inlines = [DutyItemInline]


@admin.register(DutyItem)
class DutyItemAdmin(admin.ModelAdmin):
    list_display = ["title", "duty", "experience"]
    inlines = [DutySubitemInline]

    def experience(self, obj: DutyItem) -> str:
        return str(obj.duty.experience)
