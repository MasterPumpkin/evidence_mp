from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    class_name = models.CharField(max_length=50, blank=True, null=True, help_text="Např. '3.A'")

    def __str__(self):
        return f"Profil: {self.user.username} (třída: {self.class_name})"

# Volitelný signál pro automatické vytváření profilu:
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Pokud chceš jen pro studenty (ve skupině Student) – musel bys tady ověřit, zda patří do té skupiny.
        UserProfile.objects.create(user=instance)

