from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from tanks.models import Nation, Level, Tank, BattleRecord


class Command(BaseCommand):
    help = 'Удаляет бои, танки, обычных пользователей, уровни и нации'

    def handle(self, *args, **options):
        BattleRecord.objects.all().delete()
        Tank.objects.all().delete()
        User.objects.filter(is_superuser=False, is_staff=False).delete()
        Level.objects.all().delete()
        Nation.objects.all().delete()
        self.stdout.write('База очищена')
