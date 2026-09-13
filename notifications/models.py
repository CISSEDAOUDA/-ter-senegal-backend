from django.db import models

from comptes.models import Passager


class TypeNotification(models.TextChoices):
    SMS = "SMS", "SMS"
    EMAIL = "EMAIL", "Email"


class Notification(models.Model):
    passager = models.ForeignKey(Passager, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=500)
    type = models.CharField(max_length=10, choices=TypeNotification.choices)
    date_envoi = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} a {self.passager} - {self.date_envoi:%d/%m %H:%M}"
