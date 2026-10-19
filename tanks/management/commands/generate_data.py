import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from tanks.models import Nation, Level, Crewman, Tank, BattleRecord


class Command(BaseCommand):
    help = 'Заполняет базу тестовыми данными'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=250)
        parser.add_argument('--tanks', type=int, default=1500)
        parser.add_argument('--battles', type=int, default=5000)

    def handle(self, *args, **options):
        fake = Faker('ru_RU')

        for name in ['СССР', 'Германия', 'США', 'Франция', 'Великобритания',
                     'Япония', 'Китай', 'Швеция', 'Италия', 'Польша']:
            Nation.objects.get_or_create(name=name)
        nations = list(Nation.objects.all())

        for number in range(1, 16):
            Level.objects.get_or_create(level_number=number)
        levels = list(Level.objects.all())

        crewmen = []
        for i in range(options['users']):
            username = f'user_{i + 1}'
            if User.objects.filter(username=username).exists():
                username = f'user_{i + 1}_{random.randint(1, 999)}'
            user = User.objects.create_user(username=username, password='testpass123')
            crewman = Crewman.objects.create(
                user=user,
                credits=random.randint(5000, 50000),
                garage_slots=random.randint(5, 15),
            )
            crewmen.append(crewman)

        tank_names = ['Т-34', 'КВ-1', 'ИС-2', 'Т-54', 'Т-72', 'Panther', 'Tiger I', 'Leopard 2',
                      'M4 Sherman', 'M1 Abrams', 'Centurion', 'Leclerc', 'Type 90', 'Strv 103']
        tanks_created = 0
        for i in range(options['tanks']):
            if not crewmen:
                break
            crewman = crewmen[i % len(crewmen)]
            if crewman.tanks.count() >= crewman.garage_slots:
                continue
            Tank.objects.create(
                name=f'{random.choice(tank_names)} {random.randint(1, 99)}',
                owner=crewman,
                nation=random.choice(nations),
                level=random.choice(levels),
            )
            tanks_created += 1

        tanks = list(Tank.objects.all())
        for _ in range(options['battles']):
            if not tanks:
                break
            tank = random.choice(tanks)
            tank_level = tank.level.level_number
            battle_level = random.choice([l for l in levels if abs(l.level_number - tank_level) <= 1])
            result = random.choice(['victory', 'defeat'])
            reward = battle_level.battle_reward if result == 'victory' else 0
            started_at = timezone.make_aware(fake.date_time_between(start_date='-60d', end_date='now'))

            battle = BattleRecord.objects.create(
                tank=tank,
                crewman=tank.owner,
                battle_level=battle_level,
                result=result,
                reward_earned=reward,
                finished_at=started_at + timedelta(seconds=tank_level),
            )
            BattleRecord.objects.filter(pk=battle.pk).update(started_at=started_at)

            owner = Crewman.objects.get(pk=tank.owner_id)
            owner.credits += reward
            owner.save()

        self.stdout.write(f'Создано: игроков {len(crewmen)}, танков {tanks_created}, боёв {options["battles"]}')
