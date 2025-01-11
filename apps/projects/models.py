from django.db import models
from django.conf import settings
from django.urls import reverse

class ScoringScheme(models.Model):
    year = models.CharField(max_length=20, unique=True, help_text="Školní rok, např. 2024/2025")
    
    # Vedoucí – 3 oblasti
    leader_area1_max = models.PositiveIntegerField(default=15)
    leader_area2_max = models.PositiveIntegerField(default=10)
    leader_area3_max = models.PositiveIntegerField(default=15)
    
    # Oponent – 2 oblasti
    opponent_area1_max = models.PositiveIntegerField(default=15)
    opponent_area2_max = models.PositiveIntegerField(default=15)

    active = models.BooleanField(default=False, help_text="Je toto schéma aktuálně používané?")

    def __str__(self):
        return f"Scoring {self.year} (Aktivní: {self.active})"
    


class Project(models.Model):
    STATUS_CHOICES = [
        ('pending_approval', 'Čeká na schválení'),
        ('approved', 'Schváleno'),
        ('finished', 'Dokončeno'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending_approval'
    )

    # student, který projekt založil:
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student_projects'
    )

    # vedoucí projektu (po schválení):
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leading_projects'
    )

    # případný oponent
    opponent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opponent_projects'
    )

    scheme = models.ForeignKey(
        ScoringScheme,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Scoring schema pro tento projekt (podle školního roku)"
    )

    internal_notes = models.TextField(
        blank=True,
        help_text="Poznámky viditelné pouze pro vedoucího (WYSIWYG)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edit_deadline = models.DateTimeField(null=True, blank=True, help_text="Do kdy může student upravovat projekt")


    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('projects:detail', kwargs={'pk': self.pk})



class Milestone(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Nezahájeno'),
        ('in_progress', 'Rozpracováno'),
        ('done', 'Dokončeno'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200, help_text="Krátký popis milníku")
    deadline = models.DateField(null=True, blank=True, help_text="Datum, do kdy je milník plánován")
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='not_started'
    )
    note = models.TextField(blank=True, help_text="Poznámka k milníku")

    def __str__(self):
        return f"{self.project.title}: {self.title}"



class ControlCheck(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='controls')
    date = models.DateField(help_text="Datum kontroly")
    content = models.TextField(help_text="Co bylo náplní kontroly")
    evaluation = models.CharField(max_length=200, blank=True, help_text="Hodnocení / body / slovní")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Kontrola: {self.project.title} ({self.date})"



class LeaderEvaluation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='leader_eval')
    
    # Napojení na scheme, můžeme si ho tahat i přes project.scheme, ale mít ho i tady je někdy praktičtější
    # scheme = models.ForeignKey(ScoringScheme, on_delete=models.SET_NULL, null=True, blank=True)

    # Oblasti hodnocení:
    area1_text = models.TextField(blank=True, help_text="Popis hodnocení (oblast 1)")
    area1_points = models.PositiveIntegerField(default=0)
    
    area2_text = models.TextField(blank=True, help_text="Popis hodnocení (oblast 2)")
    area2_points = models.PositiveIntegerField(default=0)
    
    area3_text = models.TextField(blank=True, help_text="Popis hodnocení (oblast 3)")
    area3_points = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Hodnocení vedoucího pro projekt: {self.project.title}"

    def clean(self):
        """
        Můžeme validovat, že areaX_points <= project.scheme.leader_areaX_max
        """
        from django.core.exceptions import ValidationError
        scheme = self.project.scheme
        if scheme:
            if self.area1_points > scheme.leader_area1_max:
                raise ValidationError("Area1 points exceed maximum allowed!")
            if self.area2_points > scheme.leader_area2_max:
                raise ValidationError("Area2 points exceed maximum allowed!")
            if self.area3_points > scheme.leader_area3_max:
                raise ValidationError("Area3 points exceed maximum allowed!")


class OpponentEvaluation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='opponent_eval')
    
    area1_text = models.TextField(blank=True, help_text="Popis hodnocení (oblast 1)")
    area1_points = models.PositiveIntegerField(default=0)
    
    area2_text = models.TextField(blank=True, help_text="Popis hodnocení (oblast 2)")
    area2_points = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Hodnocení oponenta pro projekt: {self.project.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        scheme = self.project.scheme
        if scheme:
            if self.area1_points > scheme.opponent_area1_max:
                raise ValidationError("Area1 points exceed maximum allowed (opponent)!")
            if self.area2_points > scheme.opponent_area2_max:
                raise ValidationError("Area2 points exceed maximum allowed (opponent)!")

