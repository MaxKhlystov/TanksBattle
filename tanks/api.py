import io
import math
import random
import pyotp

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Min, ProtectedError, Q, Sum
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from rest_framework import mixins, permissions, serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import BattleRecord, Crewman, Level, Nation, Tank
from .permissions import (
    IsStaffAnd2FAOrReadOnly,
    IsStaffAnd2FAVerified,
    clear_2fa,
    has_2fa,
    is_staff_with_2fa,
    set_2fa,
)
from .serializers import (
    MAX_UPLOAD_SIZE,
    BattleRecordSerializer,
    CrewmanSerializer,
    CrewmanUpdateSerializer,
    LevelSerializer,
    NationSerializer,
    TankSerializer,
)

GARAGE_SLOT_COST = 500  # цена одного дополнительного места в ангаре


def get_crewman(user):
    """Профиль игрока текущего пользователя (создаётся при первом обращении)."""
    crewman, _ = Crewman.objects.get_or_create(user=user)
    return crewman


def put_cell(ws, row, column, value):
    """Записывает значение в ячейку; строки, начинающиеся с "=", не становятся формулами."""
    cell = ws.cell(row=row, column=column, value=value)
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"
    return cell


def fill_sheet(ws, headers, rows):
    """Заполняет лист Excel: жирные заголовки, строки данных, ширина колонок по содержимому."""
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    for row, values in enumerate(rows, 2):
        for col, value in enumerate(values, 1):
            put_cell(ws, row, col, value)
    for column in ws.columns:
        width = max(len(str(cell.value)) for cell in column if cell.value is not None)
        ws.column_dimensions[column[0].column_letter].width = min(width + 2, 50)


def format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


class NationViewSet(viewsets.ModelViewSet):
    queryset = Nation.objects.all()
    serializer_class = NationSerializer
    permission_classes = [IsStaffAnd2FAOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["name"]

    def destroy(self, request, *args, **kwargs):
        nation = self.get_object()
        if nation.tanks.exists():
            return Response(
                {"error": "Нельзя удалить нацию: у неё есть танки"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            # страховка от гонки: танк мог появиться между проверкой и удалением
            return Response(
                {"error": "Нельзя удалить нацию: она используется"},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=False, methods=["GET"], url_path="stats")
    def nation_stats(self, request):
        stats = Nation.objects.annotate(tanks_count=Count("tanks")).aggregate(
            total_nations=Count("id"),
            total_tanks=Sum("tanks_count"),
            avg_tanks_per_nation=Avg("tanks_count"),
        )
        most_popular = (
            Nation.objects.annotate(tanks_count=Count("tanks"))
            .order_by("-tanks_count")
            .first()
        )
        stats["most_popular_nation"] = most_popular.name if most_popular else None
        stats["most_popular_tanks_count"] = (
            most_popular.tanks_count if most_popular else 0
        )
        if stats["avg_tanks_per_nation"] is None:
            stats["avg_tanks_per_nation"] = 0
        return Response(stats)


class LevelViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = [IsStaffAnd2FAOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["level_number"]

    @action(detail=False, methods=["GET"], url_path="stats")
    def level_stats(self, request):
        stats = Level.objects.aggregate(
            total_levels=Count("id"),
            min_level=Min("level_number"),
            max_level=Max("level_number"),
            avg_level=Avg("level_number"),
        )
        level_distribution = (
            Level.objects.annotate(tanks_count=Count("tanks"))
            .values("level_number", "tanks_count")
            .order_by("level_number")
        )
        stats["level_distribution"] = list(level_distribution)
        if stats["avg_level"] is None:
            stats["avg_level"] = 0
        return Response(stats)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        max_level = Level.objects.aggregate(Max("level_number"))["level_number__max"] or 0
        if serializer.validated_data["level_number"] != max_level + 1:
            return Response(
                {"level_number": [f"Следующий уровень должен быть {max_level + 1}"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        level = self.get_object()
        max_level = Level.objects.aggregate(Max("level_number"))["level_number__max"]
        if level.level_number != max_level:
            return Response(
                {
                    "error": f"Нельзя удалить уровень {level.level_number}. "
                    f"Можно удалить только последний уровень ({max_level})."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Бои на этом уровне: освобождаем танки (в т.ч. с других уровней), бои — поражение
            BattleRecord.cancel_pending(BattleRecord.objects.filter(battle_level=level))

            # Возврат стоимости владельцам танков этого уровня
            refund = level.creation_cost
            owner_ids = list(
                Tank.objects.filter(level=level).values_list("owner_id", flat=True)
            )
            for owner_id in owner_ids:
                Crewman.objects.filter(pk=owner_id).update(
                    credits=F("credits") + refund
                )
            total_refund = refund * len(owner_ids)

            BattleRecord.objects.filter(battle_level=level).delete()
            Tank.objects.filter(level=level).delete()
            level.delete()

        return Response(
            {
                "success": True,
                "message": f"Уровень {level.level_number} удалён. Возвращено кредитов: {total_refund}",
            }
        )


class CrewmanViewSet(GenericViewSet):
    serializer_class = CrewmanSerializer

    def get_permissions(self):
        if self.action in ["update", "list_users"]:
            return [IsStaffAnd2FAVerified()]
        if self.action == "register":
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=["POST"], url_path="expand-garage")
    def expand_garage(self, request):
        crewman = get_crewman(request.user)
        updated = Crewman.objects.filter(pk=crewman.pk, credits__gte=GARAGE_SLOT_COST).update(
            credits=F("credits") - GARAGE_SLOT_COST, garage_slots=F("garage_slots") + 1
        )
        if updated:
            crewman.refresh_from_db(fields=["garage_slots"])
            return Response({"success": True, "garage_slots": crewman.garage_slots})
        return Response(
            {"success": False, "error": "Недостаточно кредитов"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["POST"], url_path="register")
    def register(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")

        if not username or not password:
            return Response(
                {"error": "Укажите имя пользователя и пароль"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Пользователь с таким именем уже существует"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, password=password, email=email
                )
                crewman = Crewman.objects.create(user=user)
        except IntegrityError:
            # одновременная регистрация с тем же именем
            return Response(
                {"error": "Пользователь с таким именем уже существует"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        serializer = self.get_serializer(crewman)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["GET"], url_path="list-users")
    def list_users(self, request):
        crewmen = Crewman.objects.select_related("user").annotate(
            tanks_count=Count("tanks")
        )
        data = [
            {
                "id": c.id,
                "username": c.user.username,
                "credits": c.credits,
                "garage_slots": c.garage_slots,
                "tanks_count": c.tanks_count,
            }
            for c in crewmen
        ]
        return Response(data)

    def update(self, request, pk=None):
        try:
            crewman = Crewman.objects.get(pk=pk)
        except (Crewman.DoesNotExist, ValueError):
            return Response(
                {"error": "Игрок не найден"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = CrewmanUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "garage_slots" in data and data["garage_slots"] < crewman.tanks.count():
            return Response(
                {"error": "Мест в ангаре не может быть меньше, чем танков у игрока"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_fields = []
        if "credits" in data:
            crewman.credits = data["credits"]
            update_fields.append("credits")
        if "garage_slots" in data:
            crewman.garage_slots = data["garage_slots"]
            update_fields.append("garage_slots")
        if update_fields:
            crewman.save(update_fields=update_fields)

        return Response(
            {
                "success": True,
                "credits": crewman.credits,
                "garage_slots": crewman.garage_slots,
            }
        )


class TankViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = TankSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "owner__user__username",
        "owner__id",
        "nation__name",
        "level__level_number",
        "is_in_battle",
    ]

    def get_queryset(self):
        # Игрок видит только свои танки; сотрудник с 2FA — танки всех игроков.
        # Поэтому чужой танк для обычного игрока не найдётся (404) ни в update, ни в действиях.
        qs = Tank.objects.select_related("owner__user", "nation", "level")
        if is_staff_with_2fa(self.request):
            return qs
        return qs.filter(owner=get_crewman(self.request.user))

    def update(self, request, *args, **kwargs):
        if self.get_object().is_in_battle:
            raise PermissionDenied("Танк в бою")
        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=["POST"], url_path="create")
    def create_tank(self, request):
        name = (request.data.get("name") or "").strip()
        nation_id = request.data.get("nation")
        level_id = request.data.get("level")
        picture = request.FILES.get("picture")

        if not all([name, nation_id, level_id]):
            return Response(
                {"error": "Заполните название, нацию и уровень"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(name) > Tank._meta.get_field("name").max_length:
            return Response(
                {"error": "Название танка слишком длинное (максимум 100 символов)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if picture:
            if picture.size > MAX_UPLOAD_SIZE:
                return Response(
                    {"error": "Файл слишком большой (максимум 5 МБ)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                drf_serializers.ImageField().run_validation(picture)
            except DRFValidationError:
                return Response(
                    {"error": "Файл не является изображением"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        crewman = get_crewman(request.user)

        try:
            nation = Nation.objects.get(id=nation_id)
            level = Level.objects.get(id=level_id)
        except (Nation.DoesNotExist, Level.DoesNotExist, ValueError):
            return Response(
                {"error": "Неверная нация или уровень"}, status=status.HTTP_400_BAD_REQUEST
            )

        cost = level.creation_cost
        with transaction.atomic():
            paid = Crewman.objects.filter(pk=crewman.pk, credits__gte=cost).update(
                credits=F("credits") - cost
            )
            crewman.refresh_from_db(fields=["credits", "garage_slots"])
            if not paid:
                return Response(
                    {"error": f"Недостаточно кредитов. Нужно {cost}, у вас {crewman.credits}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if crewman.tanks.count() >= crewman.garage_slots:
                # ответ без исключения не откатывает транзакцию сам — откатываем списание явно
                transaction.set_rollback(True)
                return Response(
                    {"error": "Нет свободных мест в ангаре"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tank = Tank.objects.create(
                name=name, owner=crewman, nation=nation, level=level, picture=picture
            )

        serializer = self.get_serializer(tank)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["POST"], url_path="upgrade")
    def upgrade_tank(self, request, pk=None):
        tank = self.get_object()
        if tank.is_in_battle:
            return Response({"error": "Танк в бою"}, status=status.HTTP_400_BAD_REQUEST)

        next_level = Level.objects.filter(level_number=tank.level.level_number + 1).first()
        if next_level is None:
            return Response(
                {"error": "Танк уже максимального уровня"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cost = next_level.creation_cost // 2  # то же, что Level.upgrade_to_next_cost

        with transaction.atomic():
            paid = Crewman.objects.filter(
                pk=tank.owner_id, credits__gte=cost
            ).update(credits=F("credits") - cost)
            if not paid:
                tank.owner.refresh_from_db(fields=["credits"])
                return Response(
                    {"error": f"Не хватает кредитов. Нужно {cost}, у вас {tank.owner.credits}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Условие в filter защищает от гонки: танк мог уйти в бой или уже улучшиться
            upgraded = Tank.objects.filter(
                pk=tank.pk, level_id=tank.level_id, is_in_battle=False
            ).update(level=next_level)
            if not upgraded:
                transaction.set_rollback(True)
                return Response(
                    {"error": "Нельзя улучшить: танк в бою или уже улучшен"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({"success": True, "new_level": next_level.level_number})

    @action(detail=True, methods=["POST"], url_path="sell")
    def sell_tank(self, request, pk=None):
        tank = self.get_object()
        price = tank.sell_price
        if not tank.sell():
            return Response(
                {"error": "Танк уже продан или находится в бою"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "credits_earned": price})

    @action(detail=False, methods=["GET"], url_path="stats")
    def tank_stats(self, request):
        stats = Tank.objects.aggregate(
            total_tanks=Count("id"),
            avg_level=Avg("level__level_number"),
            max_level=Max("level__level_number"),
            min_level=Min("level__level_number"),
        )
        if stats["avg_level"] is None:
            stats["avg_level"] = 0
        return Response(stats)


class BattleRecordViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = BattleRecordSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["result", "battle_level__level_number", "tank__name", "crewman", "tank"]

    def get_queryset(self):
        qs = BattleRecord.objects.select_related(
            "tank__level", "crewman__user", "battle_level"
        ).order_by("-started_at")
        if is_staff_with_2fa(self.request):
            return qs
        return qs.filter(crewman=get_crewman(self.request.user))

    @action(detail=False, methods=["POST"], url_path="start")
    def start_battle(self, request):
        tank_id = request.data.get("tank_id")
        battle_level_id = request.data.get("battle_level_id")

        if not tank_id or not battle_level_id:
            return Response(
                {"error": "Выберите танк и уровень боя"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        crewman = get_crewman(request.user)
        try:
            tank = Tank.objects.select_related("level").get(id=tank_id, owner=crewman)
            battle_level = Level.objects.get(id=battle_level_id)
        except (Tank.DoesNotExist, Level.DoesNotExist, ValueError):
            return Response(
                {"error": "Неверный танк или уровень"}, status=status.HTTP_400_BAD_REQUEST
            )

        if tank.is_in_battle:
            return Response(
                {"error": "Танк уже в бою"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Доступны бои на уровне танка и на соседних уровнях (±1)
        if abs(battle_level.level_number - tank.level.level_number) > 1:
            return Response(
                {"error": "Этот уровень боя недоступен для танка"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            marked = Tank.objects.filter(
                pk=tank.pk, owner=crewman, is_in_battle=False
            ).update(is_in_battle=True)
            if not marked:
                return Response(
                    {"error": "Танк уже в бою"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            battle_record = BattleRecord.objects.create(
                tank=tank, crewman=crewman, battle_level=battle_level
            )

        serializer = BattleRecordSerializer(battle_record)
        return Response(
            {"battle_duration": battle_record.duration, **serializer.data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["GET"], url_path="remaining-time")
    def remaining_time(self, request, pk=None):
        battle = self.get_object()
        if battle.result != "pending":
            return Response(
                {"remaining": 0, "finished": True, "result": battle.result}
            )

        elapsed = (timezone.now() - battle.started_at).total_seconds()
        return Response(
            {
                "remaining": math.ceil(max(0, battle.duration - elapsed)),
                "finished": False,
                "total_duration": battle.duration,
            }
        )

    @action(detail=True, methods=["POST"], url_path="claim")
    def claim_battle(self, request, pk=None):
        battle = self.get_object()
        if battle.result != "pending":
            return Response(
                {"error": "Бой уже завершён"}, status=status.HTTP_400_BAD_REQUEST
            )

        elapsed = (timezone.now() - battle.started_at).total_seconds()
        if elapsed < battle.duration:
            remaining = math.ceil(battle.duration - elapsed)
            return Response(
                {
                    "error": f"Бой ещё не закончился. Осталось {remaining} секунд.",
                    "remaining": remaining,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tank_lvl = battle.tank.level.level_number
        battle_lvl = battle.battle_level.level_number
        if battle_lvl < tank_lvl:
            win_chance = 100
        elif battle_lvl == tank_lvl:
            win_chance = 75
        else:
            win_chance = 25

        is_victory = random.randint(1, 100) <= win_chance
        if battle.process_battle_result(is_victory) is None:
            return Response(
                {"error": "Бой уже завершён"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BattleRecordSerializer(battle)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"], url_path="stats")
    def battle_stats(self, request):
        if is_staff_with_2fa(request):
            queryset = BattleRecord.objects.all()
        else:
            queryset = BattleRecord.objects.filter(crewman=get_crewman(request.user))

        stats = queryset.aggregate(
            total_battles=Count("id"),
            victories=Count("id", filter=Q(result="victory")),
            defeats=Count("id", filter=Q(result="defeat")),
            total_reward=Sum("reward_earned"),
            avg_reward=Avg("reward_earned"),
        )
        # Процент побед считается только по завершённым боям (бои «в ожидании» не учитываются)
        finished = stats["victories"] + stats["defeats"]
        stats["win_rate"] = round(stats["victories"] / finished * 100, 1) if finished else 0
        if stats["avg_reward"] is None:
            stats["avg_reward"] = 0
        return Response(stats)

    @action(detail=True, methods=["POST"], url_path="cancel")
    def cancel_battle(self, request, pk=None):
        battle = self.get_object()
        if not BattleRecord.cancel_pending(BattleRecord.objects.filter(pk=battle.pk)):
            return Response(
                {"error": "Бой уже завершён"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"success": True, "message": "Бой отменён"})


class UserViewSet(GenericViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["GET"], url_path="info")
    def get_info(self, request):
        get_token(request._request)  # гарантирует cookie csrftoken для SPA
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
            data["second"] = has_2fa(request)  # второй фактор (2FA) подтверждён
            data["crewman_id"] = crewman.id
        return Response(data)

    @action(detail=False, methods=["POST"], url_path="login")
    def login_user(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            # при повторном входе того же пользователя Django сохраняет сессию — сбрасываем 2FA явно
            clear_2fa(request)
            return Response({"success": True})
        return Response({"success": False}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=["POST"], url_path="logout")
    def logout_user(self, request):
        logout(request)  # очищает всю сессию, в том числе отметку 2FA
        return Response({"success": True})

    @action(detail=False, methods=["GET"], url_path="get-totp")
    def get_totp(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Требуется вход"}, status=401)
        if not request.user.is_staff:
            return Response({"error": "Доступ запрещён"}, status=403)
        crewman = get_crewman(request.user)
        if crewman.totp_confirmed:
            # Секрет уже привязан: повторно его не отдаём
            return Response({"url": None, "confirmed": True})
        if not crewman.totp_key:
            crewman.totp_key = pyotp.random_base32()
            crewman.save(update_fields=["totp_key"])
        totp = pyotp.TOTP(crewman.totp_key)
        provisioning_uri = totp.provisioning_uri(
            name=request.user.username, issuer_name="TankBattles"
        )
        return Response({"url": provisioning_uri, "confirmed": False})

    @action(detail=False, methods=["POST"], url_path="second-login")
    def second_login(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Требуется вход"}, status=401)
        key = request.data.get("key")
        if not key:
            return Response({"error": "Введите код"}, status=400)
        crewman = get_crewman(request.user)
        if not crewman.totp_key:
            return Response({"error": "2FA не настроена"}, status=400)
        totp = pyotp.TOTP(crewman.totp_key)
        if totp.verify(str(key), valid_window=1):
            if not crewman.totp_confirmed:
                crewman.totp_confirmed = True
                crewman.save(update_fields=["totp_confirmed"])
            set_2fa(request)
            return Response({"success": True})
        return Response({"success": False}, status=400)

    @action(
        detail=False,
        methods=["GET"],
        url_path="export-all-stats",
        permission_classes=[IsStaffAnd2FAVerified],
    )
    def export_all_stats(self, request):
        wb = Workbook()

        ws_tanks = wb.active
        ws_tanks.title = "Танки"
        fill_sheet(
            ws_tanks,
            ["ID", "Название", "Владелец", "Нация", "Уровень", "Урон/мин", "В бою", "Создан"],
            [
                [t.id, t.name, t.owner.user.username, t.nation.name, t.level.level_number,
                 t.dpm, "Да" if t.is_in_battle else "Нет", format_dt(t.created_at)]
                for t in Tank.objects.select_related("owner__user", "nation", "level")
            ],
        )

        fill_sheet(
            wb.create_sheet("Бои"),
            ["ID", "Танк", "Игрок", "Уровень боя", "Результат", "Награда", "Начало", "Завершение"],
            [
                [b.id, b.tank.name, b.crewman.user.username, b.battle_level.level_number,
                 b.get_result_display(), b.reward_earned, format_dt(b.started_at),
                 format_dt(b.finished_at)]
                for b in BattleRecord.objects.select_related("tank", "crewman__user", "battle_level")
            ],
        )

        fill_sheet(
            wb.create_sheet("Игроки"),
            ["ID", "Имя", "Кредиты", "Слоты", "Танков", "Дата регистрации"],
            [
                [c.id, c.user.username, c.credits, c.garage_slots, c.tanks_count,
                 format_dt(c.created_at)]
                for c in Crewman.objects.select_related("user").annotate(tanks_count=Count("tanks"))
            ],
        )

        fill_sheet(
            wb.create_sheet("Нации"),
            ["ID", "Название", "Количество танков"],
            [
                [n.id, n.name, n.tanks_count]
                for n in Nation.objects.annotate(tanks_count=Count("tanks"))
            ],
        )

        fill_sheet(
            wb.create_sheet("Уровни"),
            ["ID", "Уровень", "Стоимость создания", "Награда за бой"],
            [
                [lv.id, lv.level_number, lv.creation_cost, lv.battle_reward]
                for lv in Level.objects.all()
            ],
        )

        buffer = io.BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="full_statistics.xlsx"'
        return response
