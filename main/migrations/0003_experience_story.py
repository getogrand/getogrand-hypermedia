# Generated by Django 5.0.4 on 2024-06-08 01:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_alter_duty_end_alter_duty_start_alter_experience_end_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='experience',
            name='story',
            field=models.TextField(default='placeholder'),
            preserve_default=False,
        ),
    ]
