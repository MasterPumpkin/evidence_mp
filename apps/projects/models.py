from django.db import models
from django.conf import settings
from django.urls import reverse

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edit_deadline = models.DateTimeField(null=True, blank=True, help_text="Do kdy může student upravovat projekt")


    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('projects:detail', kwargs={'pk': self.pk})
