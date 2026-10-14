# tanks/tests.py

import io
import time
from datetime import timedelta

import pyotp
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import resolve
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Nation, Level, Crewman, Tank, BattleRecord


def enable_2fa(client, user):
    """Логинит пользователя и помечает сессию как прошедшую второй фактор."""
    client.force_login(user)
    session = client.session
    session['2fa_at'] = time.time()
    session.save()


class TankAPITests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.superuser = User.objects.create_superuser(username='admin', password='admin123')
        
        self.crewman1 = Crewman.objects.create(user=self.user1, credits=10000, garage_slots=5)
        self.crewman2 = Crewman.objects.create(user=self.user2, credits=10000, garage_slots=5)
        
        self.nation = Nation.objects.create(name="TestNation")
        self.level1 = Level.objects.create(level_number=1)
        self.level2 = Level.objects.create(level_number=2)
        self.level3 = Level.objects.create(level_number=3) # <--- Добавили уровень 3
        
        self.tank1 = Tank.objects.create(
            name="Tank1", 
            owner=self.crewman1, 
            nation=self.nation, 
            level=self.level1
        )

    def test_list_tanks_owner_only(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/tanks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_tank(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            'name': 'NewTank',
            'nation': self.nation.id,
            'level': self.level1.id
        }
        response = self.client.post('/api/tanks/create/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tank.objects.count(), 2)

    def test_upgrade_tank(self):
        self.client.force_authenticate(user=self.user1)
        initial_credits = self.crewman1.credits
        response = self.client.post(f'/api/tanks/{self.tank1.id}/upgrade/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.crewman1.refresh_from_db()
        self.tank1.refresh_from_db()
        
        self.assertEqual(self.tank1.level, self.level2)
        self.assertEqual(self.crewman1.credits, initial_credits - self.level2.creation_cost // 2)

    def test_sell_tank(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/tanks/{self.tank1.id}/sell/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.crewman1.refresh_from_db()
        
        self.assertFalse(Tank.objects.filter(id=self.tank1.id).exists())
        self.assertGreater(self.crewman1.credits, 10000)

    def test_superuser_sees_all(self):
        enable_2fa(self.client, self.superuser)

        response = self.client.get('/api/tanks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1) 

class NationLevelTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='admin123')
        self.user = User.objects.create_user(username='user', password='pass123')
        self.nation = Nation.objects.create(name="Test")
        self.level = Level.objects.create(level_number=1)

    def test_admin_can_create_nation(self):
        enable_2fa(self.client, self.admin)

        response = self.client.post('/api/nations/', {'name': 'NewNation'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_create_nation(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/nations/', {'name': 'NewNation'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anyone_can_list_nations(self):
        response = self.client.get('/api/nations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RegressionTests(APITestCase):
    """Регрессионные тесты по результатам аудита."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.crewman = Crewman.objects.create(user=self.user, credits=10000, garage_slots=5)
        self.admin = User.objects.create_superuser(username='root', password='p')
        self.nation = Nation.objects.create(name='N')
        self.l1 = Level.objects.create(level_number=1)
        self.l2 = Level.objects.create(level_number=2)
        self.tank = Tank.objects.create(
            name='T', owner=self.crewman, nation=self.nation, level=self.l1
        )

    # --- C5: цена улучшения и верхний уровень ---
    def test_upgrade_price_and_top_level(self):
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(f'/api/tanks/{self.tank.id}/upgrade/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.crewman.refresh_from_db()
        self.assertEqual(self.crewman.credits, 10000 - self.l2.creation_cost // 2)

        # уровня 3 нет — дальше улучшать нельзя
        response = client.post(f'/api/tanks/{self.tank.id}/upgrade/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- C4: уровень танка нельзя поменять через PUT ---
    def test_level_is_read_only(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.put(
            f'/api/tanks/{self.tank.id}/',
            {'name': 'Renamed', 'nation': self.nation.id, 'level': self.l2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.level, self.l1)
        self.assertEqual(self.tank.name, 'Renamed')

    # --- H1: награда за бой начисляется один раз ---
    def test_claim_pays_once(self):
        tank2 = Tank.objects.create(
            name='T2', owner=self.crewman, nation=self.nation, level=self.l2
        )
        Tank.objects.filter(pk=tank2.pk).update(is_in_battle=True)
        battle = BattleRecord.objects.create(
            tank=tank2, crewman=self.crewman, battle_level=self.l1
        )
        BattleRecord.objects.filter(pk=battle.pk).update(
            started_at=timezone.now() - timedelta(seconds=60)
        )

        client = APIClient()
        client.force_authenticate(self.user)
        first = client.post(f'/api/battles/{battle.id}/claim/')
        second = client.post(f'/api/battles/{battle.id}/claim/')

        self.assertEqual(first.status_code, status.HTTP_200_OK)  # бой на уровень ниже: победа 100%
        self.assertEqual(first.data['result'], 'victory')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.crewman.refresh_from_db()
        self.assertEqual(self.crewman.credits, 10000 + self.l1.battle_reward)
        tank2.refresh_from_db()
        self.assertFalse(tank2.is_in_battle)

    # --- C2: экспорт всей статистики ---
    def test_export_all_stats_requires_staff_and_2fa(self):
        anonymous = APIClient()
        response = anonymous.get('/api/user/export-all-stats/')
        self.assertIn(response.status_code, (401, 403))

        regular = APIClient()
        regular.force_authenticate(self.user)
        self.assertEqual(
            regular.get('/api/user/export-all-stats/').status_code,
            status.HTTP_403_FORBIDDEN,
        )

        staff = User.objects.create_user(username='st', password='p', is_staff=True)
        staff_client = APIClient()
        enable_2fa(staff_client, staff)
        response = staff_client.get('/api/user/export-all-stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('spreadsheetml', response['Content-Type'])

    # --- H3: регистрация -> запрос с CSRF ---
    def test_register_then_post_with_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            '/api/crewman/register/',
            {'username': 'newbie', 'password': 'pw123456'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        token = client.cookies['csrftoken'].value
        no_token = client.post('/api/crewman/expand-garage/')
        self.assertEqual(no_token.status_code, status.HTTP_403_FORBIDDEN)

        with_token = client.post('/api/crewman/expand-garage/', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(with_token.status_code, status.HTTP_200_OK)

    def test_info_sets_csrf_cookie(self):
        response = APIClient().get('/api/user/info/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('csrftoken', response.cookies)

    # --- C3: секрет TOTP не выдаётся повторно ---
    def test_totp_secret_not_returned_after_confirmation(self):
        staff = User.objects.create_user(username='st', password='p', is_staff=True)
        client = APIClient()
        client.force_login(staff)

        response = client.get('/api/user/get-totp/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['url'].startswith('otpauth://'))
        self.assertFalse(response.data['confirmed'])

        crewman = Crewman.objects.get(user=staff)
        code = pyotp.TOTP(crewman.totp_key).now()
        response = client.post('/api/user/second-login/', {'key': code}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(client.get('/api/user/info/').data['second'])

        response = client.get('/api/user/get-totp/')
        self.assertIsNone(response.data['url'])
        self.assertTrue(response.data['confirmed'])

    def test_totp_forbidden_for_non_staff(self):
        client = APIClient()
        client.force_authenticate(self.user)
        self.assertEqual(
            client.get('/api/user/get-totp/').status_code, status.HTTP_403_FORBIDDEN
        )

    # --- H4: удаление уровня и нации ---
    def test_level_delete_frees_tank_with_pending_battle_at_that_level(self):
        Tank.objects.filter(pk=self.tank.pk).update(is_in_battle=True)
        BattleRecord.objects.create(
            tank=self.tank, crewman=self.crewman, battle_level=self.l2
        )

        client = APIClient()
        enable_2fa(client, self.admin)
        response = client.delete(f'/api/levels/{self.l2.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Level.objects.filter(pk=self.l2.pk).exists())
        self.assertEqual(BattleRecord.objects.count(), 0)
        self.tank.refresh_from_db()
        self.assertFalse(self.tank.is_in_battle)

    def test_nation_delete_blocked_when_it_has_tanks(self):
        client = APIClient()
        enable_2fa(client, self.admin)

        response = client.delete(f'/api/nations/{self.nation.id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Nation.objects.filter(pk=self.nation.pk).exists())

        empty_nation = Nation.objects.create(name='Empty')
        response = client.delete(f'/api/nations/{empty_nation.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_level_must_be_next_in_sequence(self):
        client = APIClient()
        enable_2fa(client, self.admin)
        bad = client.post('/api/levels/', {'level_number': 5}, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        good = client.post('/api/levels/', {'level_number': 3}, format='json')
        self.assertEqual(good.status_code, status.HTTP_201_CREATED)

    # --- M8: валидация обновления игрока ---
    def test_crewman_update_validation(self):
        client = APIClient()
        enable_2fa(client, self.admin)
        url = f'/api/crewman/{self.crewman.id}/'

        self.assertEqual(
            client.put(url, {'credits': ''}, format='json').status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            client.put(url, {'credits': -5}, format='json').status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        response = client.put(url, {'credits': 5000, 'garage_slots': 4}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.crewman.refresh_from_db()
        self.assertEqual(self.crewman.credits, 5000)
        self.assertEqual(self.crewman.garage_slots, 4)

    # --- H10: служебная страница со всеми данными ---
    def test_all_data_page_requires_staff_with_2fa(self):
        self.assertEqual(APIClient().get('/').status_code, status.HTTP_403_FORBIDDEN)

        client = APIClient()
        enable_2fa(client, self.admin)
        self.assertEqual(client.get('/').status_code, status.HTTP_200_OK)


class UrlTests(TestCase):
    FRONTEND_URLS = [
        '/api/tanks/create/',
        '/api/tanks/1/upgrade/',
        '/api/tanks/1/sell/',
        '/api/battles/start/',
        '/api/battles/1/claim/',
        '/api/battles/1/remaining-time/',
        '/api/battles/1/cancel/',
        '/api/crewman/register/',
        '/api/crewman/list-users/',
        '/api/crewman/expand-garage/',
        '/api/user/info/',
        '/api/user/login/',
        '/api/user/logout/',
        '/api/user/get-totp/',
        '/api/user/second-login/',
        '/api/user/logout-2fa/',
        '/api/user/export-all-stats/',
        '/api/tank-photos/',
    ]

    def test_all_frontend_urls_resolve(self):
        for url in self.FRONTEND_URLS:
            with self.subTest(url=url):
                resolve(url)


class ManagementCommandTests(TestCase):
    def test_clean_db_keeps_superuser(self):
        User.objects.create_superuser(username='root', password='p')
        player = User.objects.create_user(username='player', password='p')
        crewman = Crewman.objects.create(user=player)
        nation = Nation.objects.create(name='N')
        level = Level.objects.create(level_number=1)
        tank = Tank.objects.create(name='T', owner=crewman, nation=nation, level=level)
        BattleRecord.objects.create(tank=tank, crewman=crewman, battle_level=level)

        call_command('clean_db', '--noinput', stdout=io.StringIO())

        self.assertTrue(User.objects.filter(username='root').exists())
        self.assertFalse(User.objects.filter(username='player').exists())
        self.assertEqual(Tank.objects.count(), 0)
        self.assertEqual(BattleRecord.objects.count(), 0)
        self.assertEqual(Level.objects.count(), 0)
        self.assertEqual(Nation.objects.count(), 0)

    def test_generate_data_is_consistent(self):
        call_command('generate_data', users=3, tanks=5, battles=10, stdout=io.StringIO())

        self.assertEqual(Tank.objects.count(), 5)
        self.assertEqual(BattleRecord.objects.count(), 10)
        for battle in BattleRecord.objects.select_related('tank__level'):
            self.assertEqual(
                battle.finished_at - battle.started_at,
                timedelta(seconds=battle.tank.level.level_number),
            )
        for crewman in Crewman.objects.all():
            self.assertLessEqual(crewman.tanks.count(), crewman.garage_slots)