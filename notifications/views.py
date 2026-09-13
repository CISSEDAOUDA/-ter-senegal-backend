from rest_framework import viewsets

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Notifications simulees (pas de veritable passerelle SMS - cf.
    memoire, chapitre "difficultes rencontrees", meme logique que le
    paiement mobile). Un passager ne voit que les siennes.
    """
    serializer_class = NotificationSerializer

    def get_queryset(self):
        passager = getattr(self.request.user, "passager", None)
        if passager is None:
            return Notification.objects.none()
        return Notification.objects.filter(passager=passager).order_by("-date_envoi")
