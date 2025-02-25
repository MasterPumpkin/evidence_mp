from datetime import date
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User
from PIL import Image
from django.core.exceptions import ValidationError
import os
from django_ckeditor_5.fields import CKEditor5Field

def validate_image(image):
    # Kontrola velikosti souboru
    max_file_size = 1 * 1024 * 1024  # 1 MB
    if image.size > max_file_size:
        raise ValidationError("Obrázek je příliš velký (max. 1 MB).")

    # Kontrola typu souboru
    valid_extensions = ['.jpg', '.jpeg', '.png']
    ext = os.path.splitext(image.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Obrázek musí být ve formátu JPEG nebo PNG.")

    # Kontrola rozměrů (používáme Pillow)
    try:
        img = Image.open(image)
        max_width, max_height = 800, 400
        if img.width > max_width or img.height > max_height:
            raise ValidationError(f"Rozměry obrázku nesmí přesáhnout {max_width}x{max_height} px.")
    except IOError:
        raise ValidationError("Nepodařilo se otevřít soubor. Ujistěte se, že jde o platný obrázek.")


class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')

    pref_myprojects_default = models.BooleanField(default=False, help_text="Zobrazovat rovnou moje projekty", verbose_name="Moje projekty")
    default_year = models.CharField(
        max_length=20,
        default="2024/2025",  # nebo jiná výchozí hodnota
        help_text="Výchozí školní rok, se kterým chcete pracovat (např. '2024/2025').",
        verbose_name="Výchozí školní rok"
    )
    email_notifications = models.BooleanField(default=True, help_text="Zasílat e-mail notifikace", verbose_name="E-mail notifikace")
    consultation_text1 = models.TextField(blank=True, help_text="Předdefinovaný text konzultace #1", verbose_name="Konzultace #1")
    consultation_text2 = models.TextField(blank=True, help_text="Předdefinovaný text konzultace #2", verbose_name="Konzultace #2")
    consultation_text3 = models.TextField(blank=True, help_text="Předdefinovaný text konzultace #3", verbose_name="Konzultace #3")
    signature = models.ImageField(
            upload_to='signatures/',
            null=True,
            blank=True,
            validators=[validate_image],
            help_text="Nahrajte podpis (JPEG/PNG, max. 1 MB, max. 800x400 px).",
            verbose_name="Podpis"
        )

    def __str__(self):
        return f"Nastavení uživatele: {self.user.username}"


class ScoringScheme(models.Model):
    year = models.CharField(max_length=20, unique=True, help_text="Školní rok, např. 2024/2025", verbose_name="Školní rok")
    
    # Vedoucí – 3 oblasti
    leader_area1_max = models.PositiveIntegerField(default=15, help_text="Maximální počet bodů za oblast 1", verbose_name="Max. body oblast 1")
    leader_area2_max = models.PositiveIntegerField(default=10, help_text="Maximální počet bodů za oblast 2", verbose_name="Max. body oblast 2")
    leader_area3_max = models.PositiveIntegerField(default=15, help_text="Maximální počet bodů za oblast 3", verbose_name="Max. body oblast 3")
    
    # Oponent – 2 oblasti
    opponent_area1_max = models.PositiveIntegerField(default=15, help_text="Maximální počet bodů za oblast 1", verbose_name="Max. body oblast 1")
    opponent_area2_max = models.PositiveIntegerField(default=15, help_text="Maximální počet bodů za oblast 2", verbose_name="Max. body oblast 2")

    student_edit_deadline = models.DateTimeField(null=True, blank=True, help_text="Do kdy smí student editovat projekt")
    
    active = models.BooleanField(default=False, help_text="Je toto schéma aktuálně používané?")

    # Tři termíny
    control_deadline1 = models.DateField(null=True, blank=True, help_text="Termín kontroly #1", verbose_name="Kontrola #1")
    control_deadline2 = models.DateField(null=True, blank=True, help_text="Termín kontroly #2", verbose_name="Kontrola #2")
    control_deadline3 = models.DateField(null=True, blank=True, help_text="Termín kontroly #3", verbose_name="Kontrola #3")

    def __str__(self):
        return f"ScoreBoard {self.year} (Aktivní: {self.active})"
    


class Project(models.Model):
    STATUS_CHOICES = [
        ('pending_approval', 'Čeká na schválení'),
        ('approved', 'Schváleno'),
        ('finished', 'Dokončeno'),
        ('rejected', 'Zamítnuto'),
        ('cancelled', 'Zrušeno'),
    ]

    title = models.CharField(max_length=200, verbose_name="Název")
    description = models.TextField(verbose_name="Popis")
    assignment = models.TextField(blank=True, help_text="Oficiální zadání (needitovatelné žákem)", verbose_name="Zadání")

    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending_approval',
        verbose_name="Stav"
    )

    # student, který projekt založil:
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student_projects',
        help_text="Žák"
    )

    # vedoucí projektu (po schválení):
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leading_projects',
        help_text="Vedoucí projektu",
        verbose_name="Vedoucí"
    )

    opponent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opponent_projects',
        help_text="Oponent projektu",
        verbose_name="Oponent"
    )

    # externí vedoucí a kontaktní údaje
    external_leader = models.CharField(
        max_length=200,
        blank=True,
        help_text="Jméno externího vedoucího projektu (neregistrovaný uživatel)",
        verbose_name="Externí vedoucí"
    )
    external_leader_email = models.EmailField(
        blank=True,
        help_text="E-mail externího vedoucího",
        verbose_name="E-mail externího vedoucího"
    )
    external_leader_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Telefon externího vedoucího",
        verbose_name="Telefon externího vedoucího"
    )
    
    # externí oponent a kontaktní údaje
    external_opponent = models.CharField(
        max_length=200,
        blank=True,
        help_text="Jméno externího oponenta projektu (neregistrovaný uživatel)", 
        verbose_name="Externí oponent"
    )
    external_opponent_email = models.EmailField(
        blank=True,
        help_text="E-mail externího oponenta",
        verbose_name="E-mail externího oponenta"
    )
    external_opponent_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Telefon externího oponenta",
        verbose_name="Telefon externího oponenta"
    )

    scheme = models.ForeignKey(
        ScoringScheme,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projects',
        help_text="Scoring schema pro tento projekt (podle školního roku)",
        verbose_name="Scoring schema"
    )

    internal_notes = models.TextField(
        blank=True,
        help_text="Poznámky viditelné pouze pro vedoucího práce",
        verbose_name="Interní poznámky"
    )

    delivery_work_date = models.DateField(blank=True, null=True, help_text="Datum předání výrobku", verbose_name="Datum předání výrobku")
    delivery_documentation_date = models.DateField(blank=True, null=True, help_text="Datum předání dokumentace", verbose_name="Datum předání dokumentace")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('projects:detail', kwargs={'pk': self.pk})
    
    def leader_total_points(self):
        if hasattr(self, 'leader_eval'):
            return self.leader_eval.area1_points + self.leader_eval.area2_points + self.leader_eval.area3_points
        return "X"

    def max_leader_points(self):
        """Získá maximální počet bodů pro vedoucího ze ScoringScheme."""
        if self.scheme:
            return self.scheme.leader_area1_max + self.scheme.leader_area2_max + self.scheme.leader_area3_max  # Pole v modelu ScoringScheme
        return 0  # Pokud není přiřazený scheme

    def opponent_total_points(self):
        if hasattr(self, 'opponent_eval'):
            return self.opponent_eval.area1_points + self.opponent_eval.area2_points
        return "X"

    def max_opponent_points(self):
        """Získá maximální počet bodů pro oponenta ze ScoringScheme."""
        if self.scheme:
            return self.scheme.opponent_area1_max + self.scheme.opponent_area2_max  # Pole v modelu ScoringScheme
        return 0  # Pokud není přiřazený scheme



class Milestone(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Nezahájeno'),
        ('in_progress', 'Rozpracováno'),
        ('done', 'Dokončeno'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones', verbose_name="Projekt")
    title = models.CharField(max_length=200, help_text="Krátký popis milníku", verbose_name="Název")
    deadline = models.DateField(null=True, blank=True, help_text="Datum, do kdy je milník plánován", verbose_name="Termín")
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='not_started',
        verbose_name="Stav"
    )
    note = models.TextField(blank=True, help_text="Poznámka k milníku", verbose_name="Poznámka")

    def __str__(self):
        return f"{self.project.title}: {self.title}"
    
    @property
    def is_overdue(self):
        if self.status == 'done':
            return False
        if self.deadline and self.deadline < date.today():
            return True
        return False



class ControlCheck(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='controls', verbose_name="Projekt")
    date = models.DateField(help_text="Datum kontroly", verbose_name="Datum")
    content = models.TextField(help_text="Co bylo náplní kontroly", verbose_name="Obsah")
    evaluation = models.CharField(max_length=200, blank=True, help_text="Hodnocení / body / slovní", verbose_name="Hodnocení")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Kontrola: {self.project.title} ({self.date})"



class LeaderEvaluation(models.Model):

    SUBMISSION_STATUS_CHOICES = [
        ('on_time', 'Odevzdal v řádném termínu'),
        ('late', 'Odevzdal v náhradním termínu'),
        ('not_submitted', 'Neodevzdal v termínu')
    ]
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='leader_eval', verbose_name="Projekt")
    
    # Napojení na scheme, můžeme si ho tahat i přes project.scheme, ale mít ho i tady je někdy praktičtější
    # scheme = models.ForeignKey(ScoringScheme, on_delete=models.SET_NULL, null=True, blank=True)

    # Oblasti hodnocení:
    area1_text = models.TextField(blank=True, help_text="Úplnost, funkčnost, zpracování, obtížnost, invence", verbose_name="Kvalita výrobku (počet bodů 0 - 14)")
    area1_points = models.PositiveIntegerField(default=0, verbose_name="Body")
    
    area2_text = models.TextField(blank=True, help_text="Odborný obsah, formální stránka", verbose_name="Dokumentace (počet bodů 0 - 8)")
    area2_points = models.PositiveIntegerField(default=0, verbose_name="Body")
    
    area3_text = models.TextField(blank=True, help_text="Dodržování termínů konzultací, průběžné plnění zadaných úkolů, samostatnost, orientace v problematice", verbose_name="Průběžné kontroly plnění zadaných úkolů (počet bodů 0 - 18)")
    area3_points = models.PositiveIntegerField(default=0, verbose_name="Body")

    defense_questions = models.TextField(
        blank=True,
        help_text="Otázky k obhajobě",
        verbose_name="Otázky k obhajobě"
    )
    questions_visible = models.BooleanField(
        default=False,
        help_text="Zveřejnit otázky studentovi",
        verbose_name="Zveřejnit otázky"
    )

    export_date = models.DateField(blank=True, null=True, help_text="Datum exportu hodnocení", verbose_name="Datum exportu")
    submission_status = models.CharField(
        max_length=50,
        choices=SUBMISSION_STATUS_CHOICES,
        blank=True,
        null=True,
        verbose_name="Stav odevzdání", 
        help_text="Stav odevzdání hodnocení"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Hodnocení vedoucího pro projekt: {self.project.title}"

    def clean(self):
        """
        Můžeme validovat, že areaX_points <= project.scheme.leader_areaX_max
        """
        # from django.core.exceptions import ValidationError
        scheme = self.project.scheme
        if scheme:
            if self.area1_points > scheme.leader_area1_max:
                raise ValidationError("Přesáhli jste povolené maximum bodů za oblast 1!")
            if self.area2_points > scheme.leader_area2_max:
                raise ValidationError("Přesáhli jste povolené maximum bodů za oblast 2!")
            if self.area3_points > scheme.leader_area3_max:
                raise ValidationError("Přesáhli jste povolené maximum bodů za oblast 3!")


class OpponentEvaluation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='opponent_eval', verbose_name="Projekt")
    
    area1_text = models.TextField(blank=True, help_text="Úplnost, funkčnost, zpracování, obtížnost, invence", verbose_name="Oblast výrobku (počet bodů 0 - 12)")
    area1_points = models.PositiveIntegerField(default=0, verbose_name="Body")
    
    area2_text = models.TextField(blank=True, help_text="Odborný obsah, přehledná a srozumitelná prezentace výsledků", verbose_name="Dokumentace (počet bodů 0 - 12)")
    area2_points = models.PositiveIntegerField(default=0, verbose_name="Body")

    defense_questions = models.TextField(
        blank=True,
        help_text="Otázky k obhajobě",
        verbose_name="Otázky k obhajobě"
    )
    questions_visible = models.BooleanField(
        default=False,
        help_text="Zveřejnit otázky studentovi",
        verbose_name="Zveřejnit otázky"
    )

    export_date = models.DateField(blank=True, null=True, help_text="Datum exportu hodnocení", verbose_name="Datum exportu")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Hodnocení oponenta pro projekt: {self.project.title}"

    def clean(self):
        # from django.core.exceptions import ValidationError
        scheme = self.project.scheme
        if scheme:
            if self.area1_points > scheme.opponent_area1_max:
                raise ValidationError("Přesáhli jste povolené maximum bodů za oblast 1!")
            if self.area2_points > scheme.opponent_area2_max:
                raise ValidationError("Přesáhli jste povolené maximum bodů za oblast 2!")

