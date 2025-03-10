from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    class_name = models.CharField(max_length=50, blank=True, null=True, help_text="Např. '3.A'")

    STUDY_BRANCH_CHOICES = [
        ('-', 'Učitel'),
        ('E', 'Elektrotechnika'),
        ('IT', 'Informační technologie'),
    ]
    study_branch = models.CharField(
        max_length=2,
        choices=STUDY_BRANCH_CHOICES,
        default='-',  # pokud není zadáno, bude - (učitel)
        help_text="Obor studia (E = Elektrotechnika, IT = Informační technologie)."
    )

    title = models.CharField(
        max_length=50,
        blank=True,
        help_text="Titul (např. Mgr., Ing., Ph.D. apod.)",
        verbose_name="Titul"
    )

    school_year = models.CharField(
        max_length=20, 
        default="2024/2025",
        help_text="Školní rok studenta (např. 2024/2025, 2025/2026)", 
        verbose_name="Školní rok")

    def __str__(self):
        return f"{self.user.username} (třída: {self.class_name}, obor: {self.study_branch})"

# Volitelný signál pro automatické vytváření profilu:
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Pokud chceš jen pro studenty (ve skupině Student) – musel bys tady ověřit, zda patří do té skupiny.
        UserProfile.objects.create(user=instance)

