import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker

from tanks.models import Nation, Level, Crewman, Tank, BattleRecord


class Command(BaseCommand):
    help = 'Generate test data for the Tanks application'

    def handle(self, *args, **options):
        fake = Faker(['ru_RU'])
        
        self.stdout.write(self.style.SUCCESS('Starting data generation...'))
        
        # 1. Создание наций (если их нет)
        nations = [
            {'name': 'СССР', 'flag': None},
            {'name': 'Германия', 'flag': None},
            {'name': 'США', 'flag': None},
            {'name': 'Франция', 'flag': None},
            {'name': 'Великобритания', 'flag': None},
            {'name': 'Япония', 'flag': None},
            {'name': 'Китай', 'flag': None},
            {'name': 'Швеция', 'flag': None},
            {'name': 'Италия', 'flag': None},
            {'name': 'Польша', 'flag': None},
        ]
        
        for nation_data in nations:
            nation, created = Nation.objects.get_or_create(
                name=nation_data['name'],
                defaults={'flag': nation_data['flag']}
            )
            if created:
                self.stdout.write(f'Created nation: {nation.name}')
        
        all_nations = list(Nation.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Total nations: {len(all_nations)}'))
        
        # 2. Создание уровней (1-15)
        levels_to_create = []
        for i in range(1, 16):
            level, created = Level.objects.get_or_create(level_number=i)
            if created:
                self.stdout.write(f'Created level: {i}')
        all_levels = list(Level.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Total levels: {len(all_levels)}'))
        
        # 3. Создание пользователей и членов экипажа (минимум 50)
        self.stdout.write('Creating users and crewmen...')
        existing_users = User.objects.count()
        users_to_create = max(50, 200 - existing_users)
        
        created_users = 0
        for i in range(users_to_create):
            username = fake.unique.user_name()
            email = fake.unique.email()
            password = 'testpass123'
            
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                
                # Создаем Crewman для пользователя
                credits = random.randint(500, 5000)
                garage_slots = random.randint(3, 10)
                
                Crewman.objects.create(
                    user=user,
                    credits=credits,
                    garage_slots=garage_slots
                )
                created_users += 1
                
                if created_users % 50 == 0:
                    self.stdout.write(f'  Created {created_users} users...')
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Failed to create user {username}: {e}'))
                continue
        
        all_crewmen = list(Crewman.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Total crewmen: {len(all_crewmen)}'))
        
        # 4. Создание танков (минимум 1000)
        self.stdout.write('Creating tanks...')
        existing_tanks = Tank.objects.count()
        tanks_to_create = max(1000, 1500 - existing_tanks)
        
        tank_names = [
            'Т-34', 'КВ-1', 'ИС-2', 'Т-54', 'Т-62', 'Т-72', 'Т-90',
            'Panther', 'Tiger I', 'Tiger II', 'Leopard 1', 'Leopard 2',
            'M4 Sherman', 'M26 Pershing', 'M48 Patton', 'M1 Abrams',
            'Churchill', 'Centurion', 'Challenger 2',
            'Leclerc', 'Type 90', 'Type 10', 'K2 Black Panther',
            'Strv 103', 'Ariete', 'PT-91 Twardy'
        ]
        
        created_tanks = 0
        for i in range(tanks_to_create):
            name = random.choice(tank_names) + f' {fake.random_int(1, 99)}'
            owner = random.choice(all_crewmen)
            nation = random.choice(all_nations)
            level = random.choice(all_levels)
            is_in_battle = random.choice([True, False]) if created_tanks > 100 else False
            
            try:
                Tank.objects.create(
                    name=name,
                    owner=owner,
                    nation=nation,
                    level=level,
                    is_in_battle=is_in_battle,
                    picture=None
                )
                created_tanks += 1
                
                if created_tanks % 100 == 0:
                    self.stdout.write(f'  Created {created_tanks} tanks...')
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Failed to create tank: {e}'))
                continue
        
        all_tanks = list(Tank.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Total tanks: {len(all_tanks)}'))
        
        # 5. Создание записей о боях (минимум 2000)
        self.stdout.write('Creating battle records...')
        existing_battles = BattleRecord.objects.count()
        battles_to_create = max(2000, 3000 - existing_battles)
        
        results = ['victory', 'defeat']
        created_battles = 0
        
        for i in range(battles_to_create):
            tank = random.choice(all_tanks)
            crewman = tank.owner
            battle_level = random.choice(all_levels)
            result = random.choice(results)
            
            # Для победы начисляем награду
            reward_earned = battle_level.battle_reward if result == 'victory' else 0
            
            # Если результат victory, добавляем кредиты владельцу
            if result == 'victory' and reward_earned > 0:
                crewman.credits += reward_earned
                crewman.save()
            
            # Создаем запись о бое
            try:
                BattleRecord.objects.create(
                    tank=tank,
                    crewman=crewman,
                    battle_level=battle_level,
                    result=result,
                    reward_earned=reward_earned,
                    started_at=fake.date_time_between(start_date='-30d', end_date='now'),
                    finished_at=fake.date_time_between(start_date='-30d', end_date='now')
                )
                created_battles += 1
                
                if created_battles % 200 == 0:
                    self.stdout.write(f'  Created {created_battles} battle records...')
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Failed to create battle record: {e}'))
                continue
        
        # Освобождаем танки, которые были в бою (чтобы не было вечных боев)
        Tank.objects.filter(is_in_battle=True).update(is_in_battle=False)
        
        all_battles = BattleRecord.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Total battle records: {all_battles}'))
        
        # Итоговая статистика
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('DATA GENERATION COMPLETED!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'Нации: {Nation.objects.count()}')
        self.stdout.write(f'Уровни: {Level.objects.count()}')
        self.stdout.write(f'Пользователи: {User.objects.count()}')
        self.stdout.write(f'Члены экипажа: {Crewman.objects.count()}')
        self.stdout.write(f'Танки: {Tank.objects.count()}')
        self.stdout.write(f'Записи о боях: {BattleRecord.objects.count()}')
        self.stdout.write('='*50)