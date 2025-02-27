# Generated by Django 5.1.4 on 2025-02-25 19:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0017_alter_project_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaderevaluation',
            name='defense_questions',
            field=models.TextField(blank=True, help_text='Otázky k obhajobě', verbose_name='Otázky k obhajobě'),
        ),
        migrations.AddField(
            model_name='leaderevaluation',
            name='questions_visible',
            field=models.BooleanField(default=False, help_text='Zveřejnit otázky studentovi', verbose_name='Zveřejnit otázky'),
        ),
        migrations.AddField(
            model_name='opponentevaluation',
            name='defense_questions',
            field=models.TextField(blank=True, help_text='Otázky k obhajobě', verbose_name='Otázky k obhajobě'),
        ),
        migrations.AddField(
            model_name='opponentevaluation',
            name='questions_visible',
            field=models.BooleanField(default=False, help_text='Zveřejnit otázky studentovi', verbose_name='Zveřejnit otázky'),
        ),
    ]
