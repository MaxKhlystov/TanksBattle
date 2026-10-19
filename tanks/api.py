import io
import random
import time

import pyotp
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import BattleRecord, Crewman, Level, Nation, Tank
from .permissions import IsAdminWith2FA, IsAdminWith2FAOrReadOnly, has_2fa, is_admin
from .serializers import (
    BattleRecordSerializer,
    CrewmanSerializer,
    LevelSerializer,
    NationSerializer,
    TankSerializer,
)

def get_crewman(user):
    crewman, _ = Crewman.objects.get_or_create(user=user)
    return crewman

class NationViewSet(viewsets.ModelViewSet):
    queryset = Nation.objects.all()
    serializer_class = NationSerializer
    permission_classes = [IsAdminWith2FAOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["name"]

    def destroy(self, request, *args, **kwargs):
        nation = self.get_object()
        if nation.tanks.exists():
            return Response({"error": "Нельзя удалить нацию: у неё есть танки"}, status=400)
        nation.delete()
        return Response(status=204)

    @action(detail=False, methods=["GET"], url_path="stats")
    def nation_stats(self, request):
        total_nations = Nation.objects.count()
        total_tanks = Tank.objects.count()
        most_popular = Nation.objects.annotate(tanks_count=Count("tanks")).order_by("-tanks_count").first()
        return Response({
            "total_nations": total_nations,
            "total_tanks": total_tanks,
            "avg_tanks_per_nation": total_tanks / total_nations if total_nations else 0,
            "most_popular_nation": most_popular.name if most_popular else None,
            "most_popular_tanks_count": most_popular.tanks_count if most_popular else 0,
        })


class LevelViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = [IsAdminWith2FAOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["level_number"]

    def create(self, request, *args, **kwargs):
        max_level = Level.objects.aggregate(Max("level_number"))["level_number__max"] or 0
        if int(request.data.get("level_number", 0)) != max_level + 1:
            return Response({"error": f"Следующий уровень должен быть {max_level + 1}"}, status=400)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        level = self.get_object()
        max_level = Level.objects.aggregate(Max("level_number"))["level_number__max"]
        if level.level_number != max_level:
            return Response({"error": f"Можно удалить только последний уровень ({max_level})"}, status=400)

        for battle in BattleRecord.objects.filter(battle_level=level, result="pending"):
            battle.tank.is_in_battle = False
            battle.tank.save()

        for tank in Tank.objects.filter(level=level):
            owner = Crewman.objects.get(pk=tank.owner_id)
            owner.credits += level.creation_cost
            owner.save()

        BattleRecord.objects.filter(battle_level=level).delete()
        Tank.objects.filter(level=level).delete()
        level.delete()
        return Response({"success": True})

    @action(detail=False, methods=["GET"], url_path="stats")
    def level_stats(self, request):
        stats = Level.objects.aggregate(
            total_levels=Count("id"),
            min_level=Min("level_number"),
            max_level=Max("level_number"),
            avg_level=Avg("level_number"),
        )
        stats["level_distribution"] = list(
            Level.objects.annotate(tanks_count=Count("tanks")).values("level_number", "tanks_count")
        )
        return Response(stats)

class CrewmanViewSet(GenericViewSet):
    serializer_class = CrewmanSerializer

    def get_permissions(self):
        if self.action in ["update", "list_users"]:
            return [IsAdminWith2FA()]
        if self.action == "register":
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=["POST"], url_path="expand-garage")
    def expand_garage(self, request):
        crewman = get_crewman(request.user)
        if crewman.credits < 500:
            return Response({"error": "Недостаточно кредитов"}, status=400)
        crewman.credits -= 500
        crewman.garage_slots += 1
        crewman.save()
        return Response({"success": True, "garage_slots": crewman.garage_slots})

    @action(detail=False, methods=["POST"], url_path="register")
    def register(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")

        if not username or not password:
            return Response({"error": "Укажите имя пользователя и пароль"}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({"error": "Пользователь с таким именем уже существует"}, status=400)

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password, email=email)
            crewman = Crewman.objects.create(user=user)
        login(request, user)
        return Response(CrewmanSerializer(crewman).data, status=201)

    @action(detail=False, methods=["GET"], url_path="list-users")
    def list_users(self, request):
        data = []
        for crewman in Crewman.objects.all():
            data.append({
                "id": crewman.id,
                "username": crewman.user.username,
                "credits": crewman.credits,
                "garage_slots": crewman.garage_slots,
                "tanks_count": crewman.tanks.count(),
            })
        return Response(data)

    def update(self, request, pk=None):
        crewman = get_object_or_404(Crewman, pk=pk)
        credits = int(request.data.get("credits", crewman.credits))
        garage_slots = int(request.data.get("garage_slots", crewman.garage_slots))

        if credits < 0:
            return Response({"error": "Кредиты не могут быть отрицательными"}, status=400)
        if garage_slots < crewman.tanks.count() or garage_slots < 1:
            return Response({"error": "Мест в ангаре не может быть меньше, чем танков у игрока"}, status=400)

        crewman.credits = credits
        crewman.garage_slots = garage_slots
        crewman.save()
        return Response({"success": True, "credits": crewman.credits, "garage_slots": crewman.garage_slots})

class TankViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = TankSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["owner__id", "nation__name", "level__level_number", "is_in_battle"]

    def get_queryset(self):
        if is_admin(self.request):
            return Tank.objects.all()
        return Tank.objects.filter(owner=get_crewman(self.request.user))

    def update(self, request, *args, **kwargs):
        if self.get_object().is_in_battle:
            return Response({"error": "Танк в бою"}, status=400)
        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=["POST"], url_path="create")
    def create_tank(self, request):
        name = request.data.get("name")
        nation_id = request.data.get("nation")
        level_id = request.data.get("level")
        if not name or not nation_id or not level_id:
            return Response({"error": "Заполните название, нацию и уровень"}, status=400)

        nation = get_object_or_404(Nation, id=nation_id)
        level = get_object_or_404(Level, id=level_id)
        crewman = get_crewman(request.user)

        if crewman.credits < level.creation_cost:
            return Response({"error": f"Недостаточно кредитов. Нужно {level.creation_cost}"}, status=400)
        if crewman.tanks.count() >= crewman.garage_slots:
            return Response({"error": "Нет свободных мест в ангаре"}, status=400)

        crewman.credits -= level.creation_cost
        crewman.save()
        tank = Tank.objects.create(
            name=name,
            owner=crewman,
            nation=nation,
            level=level,
            picture=request.FILES.get("picture"),
        )
        return Response(TankSerializer(tank).data, status=201)

    @action(detail=True, methods=["POST"], url_path="upgrade")
    def upgrade_tank(self, request, pk=None):
        tank = self.get_object()
        if tank.is_in_battle:
            return Response({"error": "Танк в бою"}, status=400)

        next_level = Level.objects.filter(level_number=tank.level.level_number + 1).first()
        if next_level is None:
            return Response({"error": "Танк уже максимального уровня"}, status=400)

        cost = next_level.creation_cost // 2
        owner = tank.owner
        if owner.credits < cost:
            return Response({"error": f"Не хватает кредитов. Нужно {cost}"}, status=400)

        owner.credits -= cost
        owner.save()
        tank.level = next_level
        tank.save()
        return Response({"success": True, "new_level": next_level.level_number})

    @action(detail=True, methods=["POST"], url_path="sell")
    def sell_tank(self, request, pk=None):
        tank = self.get_object()
        if tank.is_in_battle:
            return Response({"error": "Танк в бою"}, status=400)

        price = tank.sell_price
        owner = tank.owner
        owner.credits += price
        owner.save()
        tank.delete()
        return Response({"success": True, "credits_earned": price})

    @action(detail=False, methods=["GET"], url_path="stats")
    def tank_stats(self, request):
        stats = Tank.objects.aggregate(
            total_tanks=Count("id"),
            avg_level=Avg("level__level_number"),
            max_level=Max("level__level_number"),
            min_level=Min("level__level_number"),
        )
        return Response(stats)

class BattleRecordViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = BattleRecordSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["result", "crewman", "tank"]

    def get_queryset(self):
        if is_admin(self.request):
            return BattleRecord.objects.all()
        return BattleRecord.objects.filter(crewman=get_crewman(self.request.user))

    @action(detail=False, methods=["POST"], url_path="start")
    def start_battle(self, request):
        crewman = get_crewman(request.user)
        tank = get_object_or_404(Tank, id=request.data.get("tank_id"), owner=crewman)
        battle_level = get_object_or_404(Level, id=request.data.get("battle_level_id"))

        if tank.is_in_battle:
            return Response({"error": "Танк уже в бою"}, status=400)
        if abs(battle_level.level_number - tank.level.level_number) > 1:
            return Response({"error": "Этот уровень боя недоступен для танка"}, status=400)

        tank.is_in_battle = True
        tank.save()
        battle = BattleRecord.objects.create(tank=tank, crewman=crewman, battle_level=battle_level)

        data = BattleRecordSerializer(battle).data
        data["battle_duration"] = tank.level.level_number
        return Response(data, status=201)

    @action(detail=True, methods=["POST"], url_path="claim")
    def claim_battle(self, request, pk=None):
        battle = self.get_object()
        if battle.result != "pending":
            return Response({"error": "Бой уже завершён"}, status=400)

        tank_level = battle.tank.level.level_number
        battle_level = battle.battle_level.level_number
        elapsed = (timezone.now() - battle.started_at).total_seconds()
        if elapsed < tank_level:
            return Response({"error": "Бой ещё не закончился"}, status=400)

        if battle_level < tank_level:
            win_chance = 100
        elif battle_level == tank_level:
            win_chance = 75
        else:
            win_chance = 25

        if random.randint(1, 100) <= win_chance:
            battle.result = "victory"
            battle.reward_earned = battle.battle_level.battle_reward
            battle.crewman.credits += battle.reward_earned
            battle.crewman.save()
        else:
            battle.result = "defeat"
        battle.finished_at = timezone.now()
        battle.save()

        battle.tank.is_in_battle = False
        battle.tank.save()
        return Response(BattleRecordSerializer(battle).data)

    @action(detail=True, methods=["POST"], url_path="cancel")
    def cancel_battle(self, request, pk=None):
        battle = self.get_object()
        if battle.result != "pending":
            return Response({"error": "Бой уже завершён"}, status=400)

        battle.result = "defeat"
        battle.finished_at = timezone.now()
        battle.save()
        battle.tank.is_in_battle = False
        battle.tank.save()
        return Response({"success": True})

    @action(detail=False, methods=["GET"], url_path="stats")
    def battle_stats(self, request):
        battles = self.get_queryset()
        stats = battles.aggregate(
            total_battles=Count("id"),
            victories=Count("id", filter=Q(result="victory")),
            defeats=Count("id", filter=Q(result="defeat")),
            total_reward=Sum("reward_earned"),
            avg_reward=Avg("reward_earned"),
        )
        finished = stats["victories"] + stats["defeats"]
        stats["win_rate"] = round(stats["victories"] / finished * 100, 1) if finished else 0
        return Response(stats)

class UserViewSet(GenericViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["GET"], url_path="info")
    def get_info(self, request):
        get_token(request)
        data = {
            "username": request.user.username if request.user.is_authenticated else None,
            "is_authenticated": request.user.is_authenticated,
            "is_staff": request.user.is_staff,
            "crewman_id": None,
        }
        if request.user.is_authenticated:
            crewman = get_crewman(request.user)
            data["credits"] = crewman.credits
            data["garage_slots"] = crewman.garage_slots
            data["second"] = has_2fa(request)
            data["crewman_id"] = crewman.id
        return Response(data)

    @action(detail=False, methods=["POST"], url_path="login")
    def login_user(self, request):
        user = authenticate(username=request.data.get("username"), password=request.data.get("password"))
        if user is None:
            return Response({"success": False}, status=401)
        login(request, user)
        request.session.pop("2fa_at", None)
        return Response({"success": True})

    @action(detail=False, methods=["POST"], url_path="logout")
    def logout_user(self, request):
        logout(request)
        return Response({"success": True})

    @action(detail=False, methods=["GET"], url_path="get-totp")
    def get_totp(self, request):
        if not request.user.is_staff:
            return Response({"error": "Доступ запрещён"}, status=403)
        crewman = get_crewman(request.user)
        if crewman.totp_confirmed:
            return Response({"url": None, "confirmed": True})
        if not crewman.totp_key:
            crewman.totp_key = pyotp.random_base32()
            crewman.save()
        url = pyotp.TOTP(crewman.totp_key).provisioning_uri(name=request.user.username, issuer_name="TankBattles")
        return Response({"url": url, "confirmed": False})

    @action(detail=False, methods=["POST"], url_path="second-login")
    def second_login(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Требуется вход"}, status=401)
        crewman = get_crewman(request.user)
        if not crewman.totp_key:
            return Response({"error": "2FA не настроена"}, status=400)
        if not pyotp.TOTP(crewman.totp_key).verify(str(request.data.get("key"))):
            return Response({"success": False}, status=400)
        crewman.totp_confirmed = True
        crewman.save()
        request.session["2fa_at"] = time.time()
        return Response({"success": True})

    @action(detail=False, methods=["GET"], url_path="export-all-stats", permission_classes=[IsAdminWith2FA])
    def export_all_stats(self, request):
        wb = Workbook()

        ws = wb.active
        ws.title = "Танки"
        ws.append(["ID", "Название", "Владелец", "Нация", "Уровень", "Урон/мин", "В бою", "Создан"])
        for t in Tank.objects.all():
            ws.append([t.id, t.name, t.owner.user.username, t.nation.name, t.level.level_number,
                       t.dpm, "Да" if t.is_in_battle else "Нет", t.created_at.strftime("%Y-%m-%d %H:%M")])

        ws = wb.create_sheet("Бои")
        ws.append(["ID", "Танк", "Игрок", "Уровень боя", "Результат", "Награда", "Начало"])
        for b in BattleRecord.objects.all():
            ws.append([b.id, b.tank.name, b.crewman.user.username, b.battle_level.level_number,
                       b.get_result_display(), b.reward_earned, b.started_at.strftime("%Y-%m-%d %H:%M")])

        ws = wb.create_sheet("Игроки")
        ws.append(["ID", "Имя", "Кредиты", "Слоты", "Танков"])
        for c in Crewman.objects.all():
            ws.append([c.id, c.user.username, c.credits, c.garage_slots, c.tanks.count()])

        ws = wb.create_sheet("Нации")
        ws.append(["ID", "Название", "Количество танков"])
        for n in Nation.objects.all():
            ws.append([n.id, n.name, n.tanks.count()])

        ws = wb.create_sheet("Уровни")
        ws.append(["ID", "Уровень", "Стоимость создания", "Награда за бой"])
        for lv in Level.objects.all():
            ws.append([lv.id, lv.level_number, lv.creation_cost, lv.battle_reward])

        buffer = io.BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="full_statistics.xlsx"'
        return response