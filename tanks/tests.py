import io
import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Nation, Level, Crewman, Tank, BattleRecord


def enable_2fa(client, user):
    client.force_login(user)
    session = client.session
    session['2fa_at'] = time.time()
    session.save()


class TankTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.crewman1 = Crewman.objects.create(user=self.user1, credits=10000, garage_slots=5)
        self.crewman2 = Crewman.objects.create(user=self.user2, credits=10000, garage_slots=5)
        self.nation = Nation.objects.create(name='СССР')
        self.level1 = Level.objects.create(level_number=1)
        self.level2 = Level.objects.create(level_number=2)
        self.tank1 = Tank.objects.create(name='Т-34', owner=self.crewman1, nation=self.nation, level=self.level1)
        self.tank2 = Tank.objects.create(name='ИС-2', owner=self.crewman2, nation=self.nation, level=self.level1)

    def test_list_only_own_tanks(self):
        self.client.force_authenticate(self.user1)
        response = self.client.get('/api/tanks/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([t['id'] for t in response.data], [self.tank1.id])

    def test_admin_sees_all_tanks(self):
        admin = User.objects.create_user(username='admin', password='p', is_staff=True)
        enable_2fa(self.client, admin)
        response = self.client.get('/api/tanks/')
        self.assertEqual(len(response.data), 2)

    def test_create_tank(self):
        self.client.force_authenticate(self.user1)
        response = self.client.post('/api/tanks/create/', {
            'name': 'КВ-1', 'nation': self.nation.id, 'level': self.level1.id
        })
        self.assertEqual(response.status_code, 201)
        self.crewman1.refresh_from_db()
        self.assertEqual(self.crewman1.credits, 10000 - self.level1.creation_cost)

    def test_upgrade_tank(self):
        self.client.force_authenticate(self.user1)
        response = self.client.post(f'/api/tanks/{self.tank1.id}/upgrade/')
        self.assertEqual(response.status_code, 200)
        self.tank1.refresh_from_db()
        self.crewman1.refresh_from_db()
        self.assertEqual(self.tank1.level, self.level2)
        self.assertEqual(self.crewman1.credits, 10000 - self.level2.creation_cost // 2)

        response = self.client.post(f'/api/tanks/{self.tank1.id}/upgrade/')
        self.assertEqual(response.status_code, 400)

    def test_sell_tank(self):
        self.client.force_authenticate(self.user1)
        response = self.client.post(f'/api/tanks/{self.tank1.id}/sell/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tank.objects.filter(id=self.tank1.id).exists())
        self.crewman1.refresh_from_db()
        self.assertEqual(self.crewman1.credits, 10000 + self.level1.creation_cost // 2)

    def test_cannot_sell_foreign_tank(self):
        self.client.force_authenticate(self.user1)
        response = self.client.post(f'/api/tanks/{self.tank2.id}/sell/')
        self.assertEqual(response.status_code, 404)

    def test_level_cannot_be_changed_by_put(self):
        self.client.force_authenticate(self.user1)
        response = self.client.put(f'/api/tanks/{self.tank1.id}/', {
            'name': 'Новое имя', 'nation': self.nation.id, 'level': self.level2.id
        })
        self.assertEqual(response.status_code, 200)
        self.tank1.refresh_from_db()
        self.assertEqual(self.tank1.name, 'Новое имя')
        self.assertEqual(self.tank1.level, self.level1)


class NationLevelTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='p', is_staff=True)
        self.user = User.objects.create_user(username='user', password='p')
        self.crewman = Crewman.objects.create(user=self.user, credits=10000)
        self.nation = Nation.objects.create(name='СССР')
        self.level1 = Level.objects.create(level_number=1)
        self.level2 = Level.objects.create(level_number=2)

    def test_anyone_can_list_nations(self):
        response = APIClient().get('/api/nations/')
        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_nation(self):
        enable_2fa(self.client, self.admin)
        response = self.client.post('/api/nations/', {'name': 'Германия'})
        self.assertEqual(response.status_code, 201)

    def test_user_cannot_create_nation(self):
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/nations/', {'name': 'Германия'})
        self.assertEqual(response.status_code, 403)

    def test_cannot_delete_nation_with_tanks(self):
        Tank.objects.create(name='Т-34', owner=self.crewman, nation=self.nation, level=self.level1)
        enable_2fa(self.client, self.admin)
        response = self.client.delete(f'/api/nations/{self.nation.id}/')
        self.assertEqual(response.status_code, 400)

        empty = Nation.objects.create(name='Франция')
        response = self.client.delete(f'/api/nations/{empty.id}/')
        self.assertEqual(response.status_code, 204)

    def test_level_must_be_next(self):
        enable_2fa(self.client, self.admin)
        self.assertEqual(self.client.post('/api/levels/', {'level_number': 5}).status_code, 400)
        self.assertEqual(self.client.post('/api/levels/', {'level_number': 3}).status_code, 201)

    def test_delete_level_frees_tank(self):
        tank = Tank.objects.create(name='Т-34', owner=self.crewman, nation=self.nation, level=self.level1, is_in_battle=True)
        BattleRecord.objects.create(tank=tank, crewman=self.crewman, battle_level=self.level2)
        enable_2fa(self.client, self.admin)
        response = self.client.delete(f'/api/levels/{self.level2.id}/')
        self.assertEqual(response.status_code, 200)
        tank.refresh_from_db()
        self.assertFalse(tank.is_in_battle)
        self.assertEqual(BattleRecord.objects.count(), 0)


class BattleTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='p')
        self.crewman = Crewman.objects.create(user=self.user, credits=10000)
        self.nation = Nation.objects.create(name='СССР')
        self.level1 = Level.objects.create(level_number=1)
        self.level2 = Level.objects.create(level_number=2)
        self.level3 = Level.objects.create(level_number=3)
        self.tank = Tank.objects.create(name='Т-34', owner=self.crewman, nation=self.nation, level=self.level2)
        self.client.force_authenticate(self.user)

    def test_start_battle(self):
        response = self.client.post('/api/battles/start/', {'tank_id': self.tank.id, 'battle_level_id': self.level1.id})
        self.assertEqual(response.status_code, 201)
        self.tank.refresh_from_db()
        self.assertTrue(self.tank.is_in_battle)

    def test_cannot_start_battle_on_wrong_level(self):
        level5 = Level.objects.create(level_number=5)
        response = self.client.post('/api/battles/start/', {'tank_id': self.tank.id, 'battle_level_id': level5.id})
        self.assertEqual(response.status_code, 400)

    def test_claim_pays_once(self):
        self.tank.is_in_battle = True
        self.tank.save()
        battle = BattleRecord.objects.create(tank=self.tank, crewman=self.crewman, battle_level=self.level1)
        BattleRecord.objects.filter(pk=battle.pk).update(started_at=timezone.now() - timedelta(seconds=60))

        first = self.client.post(f'/api/battles/{battle.id}/claim/')
        second = self.client.post(f'/api/battles/{battle.id}/claim/')
        self.assertEqual(first.data['result'], 'victory')
        self.assertEqual(second.status_code, 400)
        self.crewman.refresh_from_db()
        self.assertEqual(self.crewman.credits, 10000 + self.level1.battle_reward)

    def test_cancel_battle(self):
        self.tank.is_in_battle = True
        self.tank.save()
        battle = BattleRecord.objects.create(tank=self.tank, crewman=self.crewman, battle_level=self.level1)
        response = self.client.post(f'/api/battles/{battle.id}/cancel/')
        self.assertEqual(response.status_code, 200)
        battle.refresh_from_db()
        self.tank.refresh_from_db()
        self.assertEqual(battle.result, 'defeat')
        self.assertFalse(self.tank.is_in_battle)


class UserTests(APITestCase):
    def test_register(self):
        response = self.client.post('/api/crewman/register/', {'username': 'newbie', 'password': 'pw123456'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Crewman.objects.get(user__username='newbie').credits, 1000)

    def test_totp_only_for_staff(self):
        user = User.objects.create_user(username='user', password='p')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get('/api/user/get-totp/').status_code, 403)

    def test_export_requires_2fa(self):
        admin = User.objects.create_user(username='admin', password='p', is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/api/user/export-all-stats/').status_code, 403)
        enable_2fa(self.client, admin)
        self.assertEqual(self.client.get('/api/user/export-all-stats/').status_code, 200)

    def test_all_data_page_requires_2fa(self):
        self.assertEqual(self.client.get('/').status_code, 403)
        admin = User.objects.create_user(username='admin', password='p', is_staff=True)
        enable_2fa(self.client, admin)
        self.assertEqual(self.client.get('/').status_code, 200)


class CommandTests(TestCase):
    def test_clean_db(self):
        User.objects.create_superuser(username='root', password='p')
        player = User.objects.create_user(username='player', password='p')
        crewman = Crewman.objects.create(user=player)
        nation = Nation.objects.create(name='СССР')
        level = Level.objects.create(level_number=1)
        Tank.objects.create(name='Т-34', owner=crewman, nation=nation, level=level)

        call_command('clean_db', stdout=io.StringIO())

        self.assertTrue(User.objects.filter(username='root').exists())
        self.assertFalse(User.objects.filter(username='player').exists())
        self.assertEqual(Tank.objects.count(), 0)
        self.assertEqual(Level.objects.count(), 0)

    def test_generate_data(self):
        call_command('generate_data', users=3, tanks=5, battles=10, stdout=io.StringIO())
        self.assertEqual(Tank.objects.count(), 5)
        self.assertEqual(BattleRecord.objects.count(), 10)
