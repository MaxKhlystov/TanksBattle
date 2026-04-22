import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker

from tanks.models import Nation, Level, Crewman, Tank, BattleRecord


class Command(BaseCommand):
    help = 'Generate test data for the Tanks application'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=250, help='Number of regular users to create')
        parser.add_argument('--tanks', type=int, default=1500, help='Total number of tanks to create')
        parser.add_argument('--battles', type=int, default=5000, help='Total number of battle records to create')

    def handle(self, *args, **options):
        fake = Faker(['ru_RU'])
        users_count = options['users']
        tanks_total = options['tanks']
        battles_total = options['battles']

        self.stdout.write(self.style.SUCCESS('Starting data generation...'))

        nations_data = [
            'СССР', 'Германия', 'США', 'Франция', 'Великобритания',
            'Япония', 'Китай', 'Швеция', 'Италия', 'Польша'
        ]
        for name in nations_data:
            Nation.objects.get_or_create(name=name)
        nations = list(Nation.objects.all())
        self.stdout.write(f'✓ Nations: {len(nations)}')

        for i in range(1, 16):
            Level.objects.get_or_create(level_number=i)
        levels = list(Level.objects.all())
        self.stdout.write(f'✓ Levels: {len(levels)}')

        self.stdout.write(f'Creating {users_count} regular users...')
        crewmen_list = []
        existing_usernames = set(User.objects.values_list('username', flat=True))

        for i in range(users_count):
            username = f"user_{i+1}"
            while username in existing_usernames:
                username = f"user_{i+1}_{random.randint(1,999)}"
            existing_usernames.add(username)
            email = f"{username}@example.com"
            password = 'testpass123'

            user = User.objects.create_user(username=username, email=email, password=password)
            user.is_staff = False
            user.is_superuser = False
            user.save()

            credits = random.randint(5000, 50000)
            garage_slots = random.randint(5, 15)
            crewman = Crewman.objects.create(user=user, credits=credits, garage_slots=garage_slots)
            crewmen_list.append(crewman)

            if (i+1) % 50 == 0:
                self.stdout.write(f'  Created {i+1} users...')

        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(crewmen_list)} crewmen'))
        
        self.stdout.write(f'Creating {tanks_total} tanks...')
        tank_names_pool = [
            'Т-34', 'КВ-1', 'ИС-2', 'Т-54', 'Т-62', 'Т-72', 'Т-90',
            'Panther', 'Tiger I', 'Tiger II', 'Leopard 1', 'Leopard 2',
            'M4 Sherman', 'M26 Pershing', 'M48 Patton', 'M1 Abrams',
            'Churchill', 'Centurion', 'Challenger 2',
            'Leclerc', 'Type 90', 'Type 10', 'K2 Black Panther',
            'Strv 103', 'Ariete', 'PT-91 Twardy'
        ]

        tanks_created = 0
        for i in range(tanks_total):
            crewman = random.choice(crewmen_list)
            name = random.choice(tank_names_pool) + f' {random.randint(1, 99)}'
            nation = random.choice(nations)
            level = random.choice(levels)

            Tank.objects.create(
                name=name,
                owner=crewman,
                nation=nation,
                level=level,
                is_in_battle=False,
                picture=None
            )
            tanks_created += 1
            if tanks_created % 200 == 0:
                self.stdout.write(f'  Created {tanks_created} tanks...')

        self.stdout.write(self.style.SUCCESS(f'✓ Created {tanks_created} tanks'))

        self.stdout.write(f'Creating {battles_total} battle records...')
        all_tanks = list(Tank.objects.all())
        battles_created = 0

        for i in range(battles_total):
            tank = random.choice(all_tanks)
            battle_level = random.choice(levels)
            result = random.choice(['victory', 'defeat'])
            reward = battle_level.battle_reward if result == 'victory' else 0

            started_at = fake.date_time_between(start_date='-60d', end_date='now')
            finished_at = started_at + timedelta(seconds=random.randint(30, 300))

            BattleRecord.objects.create(
                tank=tank,
                crewman=tank.owner,
                battle_level=battle_level,
                result=result,
                reward_earned=reward,
                started_at=started_at,
                finished_at=finished_at
            )
            battles_created += 1
            if battles_created % 500 == 0:
                self.stdout.write(f'  Created {battles_created} battles...')

        self.stdout.write(self.style.SUCCESS(f'✓ Created {battles_created} battle records'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('DATA GENERATION COMPLETED!'))
        self.stdout.write('='*50)
        self.stdout.write(f'Нации: {Nation.objects.count()}')
        self.stdout.write(f'Уровни: {Level.objects.count()}')
        self.stdout.write(f'Обычные пользователи: {Crewman.objects.exclude(user__is_superuser=True).count()}')
        self.stdout.write(f'Танки: {Tank.objects.count()}')
        self.stdout.write(f'Записи о боях: {BattleRecord.objects.count()}')
        self.stdout.write('='*50)