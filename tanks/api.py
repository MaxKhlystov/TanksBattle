import io
import math
import random
import pyotp

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, ProtectedError, Q, Sum
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from rest_framework import mixins, permissions, serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import BattleRecord, Crewman, Level, Nation, Tank, TankPhoto
from .permissions import IsStaffAnd2FAVerified, clear_2fa, has_2fa, set_2fa
from .serializers import (
    BattleRecordSerializer,
    CrewmanSerializer,
    LevelSerializer,
    NationSerializer,
    TankPhotoSerializer,
    TankSerializer,
)

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 МБ


def put_cell(ws, row, column, value):
    """Записывает значение в ячейку; строки, начинающиеся с "=", не становятся формулами."""
    cell = ws.cell(row=row, column=column, value=value)
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"
    return cell


class CrewmanUpdateSerializer(drf_serializers.Serializer):
    credits = drf_serializers.IntegerField(min_value=0, required=False)
    garage_slots = drf_serializers.IntegerField(min_value=1, required=False)


class NationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Nation.objects.all()
    serializer_class = NationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["name"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsStaffAnd2FAVerified()]
        return [permissions.AllowAny()]

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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["level_number"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsStaffAnd2FAVerified()]
        return [permissions.AllowAny()]

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

        try:
            with transaction.atomic():
                # Бои на этом уровне: освобождаем танки (в т.ч. с других уровней), бои — поражение
                pending = BattleRecord.objects.filter(battle_level=level, result="pending")
                Tank.objects.filter(pk__in=pending.values("tank_id")).update(
                    is_in_battle=False
                )
                pending.update(
                    result="defeat", reward_earned=0, finished_at=timezone.now()
                )

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
        except ProtectedError:
            return Response(
                {"error": "Нельзя удалить уровень: он используется"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "success": True,
                "message": f"Уровень {level.level_number} удалён. Возвращено кредитов: {total_refund}",
            }
        )


class CrewmanViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CrewmanSerializer
    queryset = Crewman.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["user__username", "credits", "garage_slots"]

    def get_permissions(self):
        if self.action in ["update", "partial_update", "list_users"]:
            return [IsStaffAnd2FAVerified()]
        if self.action == "register":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_object(self):
        crewman, _ = Crewman.objects.get_or_create(user=self.request.user)
        return crewman

    @action(detail=False, methods=["GET"], url_path="profile")
    def profile(self, request):
        crewman = self.get_object()
        serializer = self.get_serializer(crewman)
        return Response(serializer.data)

    @action(detail=False, methods=["POST"], url_path="expand-garage")
    def expand_garage(self, request):
        crewman = self.get_object()
        cost = 500
        updated = Crewman.objects.filter(pk=crewman.pk, credits__gte=cost).update(
            credits=F("credits") - cost, garage_slots=F("garage_slots") + 1
        )
        if updated:
            crewman.refresh_from_db(fields=["garage_slots"])
            return Response({"success": True, "garage_slots": crewman.garage_slots})
        return Response(
            {"success": False, "error": "Not enough credits"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["POST"], url_path="register")
    def register(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")

        if not username or not password:
            return Response(
                {"error": "Username and password required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, password=password, email=email
                )
                crewman = Crewman.objects.create(user=user, credits=1000, garage_slots=3)
            login(request, user)
            serializer = self.get_serializer(crewman)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception:
            return Response(
                {"error": "Не удалось зарегистрироваться"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
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
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = TankSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "owner__user__username",
        "owner__id",
        "nation__name",
        "level__level_number",
        "is_in_battle",
    ]

    def get_queryset(self):
        qs = Tank.objects.select_related(
            "owner__user", "nation", "level"
        ).prefetch_related("photos")
        user = self.request.user
        if not user.is_superuser or not has_2fa(self.request):
            crewman, _ = Crewman.objects.get_or_create(user=user)
            return qs.filter(owner=crewman)
        return qs.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def update(self, request, *args, **kwargs):
        tank = self.get_object()
        if tank.owner.user != request.user and not request.user.is_superuser:
            raise PermissionDenied("You do not own this tank.")
        if request.user.is_superuser and tank.owner.user != request.user:
            if not has_2fa(request):
                raise PermissionDenied("2FA required for editing other users' tanks.")
        if tank.is_in_battle:
            raise PermissionDenied("Танк в бою")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=["POST"], url_path="create")
    def create_tank(self, request):
        name = request.data.get("name")
        nation_id = request.data.get("nation")
        level_id = request.data.get("level")
        picture = request.FILES.get("picture")

        if not all([name, nation_id, level_id]):
            return Response(
                {"error": "Missing fields"}, status=status.HTTP_400_BAD_REQUEST
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

        crewman, _ = Crewman.objects.get_or_create(user=self.request.user)

        try:
            nation = Nation.objects.get(id=nation_id)
            level = Level.objects.get(id=level_id)
        except (Nation.DoesNotExist, Level.DoesNotExist, ValueError):
            return Response(
                {"error": "Invalid nation or level"}, status=status.HTTP_400_BAD_REQUEST
            )

        cost = level.creation_cost
        with transaction.atomic():
            paid = Crewman.objects.filter(pk=crewman.pk, credits__gte=cost).update(
                credits=F("credits") - cost
            )
            crewman.refresh_from_db(fields=["credits", "garage_slots"])
            if not paid:
                return Response(
                    {
                        "error": f"Not enough credits. Need {cost}, you have {crewman.credits}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if crewman.tanks.count() >= crewman.garage_slots:
                transaction.set_rollback(True)
                return Response(
                    {"error": "No free garage slots"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tank = Tank.objects.create(
                name=name,
                owner=crewman,
                nation=nation,
                level=level,
                is_in_battle=False,
                picture=picture,
            )

        serializer = self.get_serializer(tank)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["POST"], url_path="upgrade")
    def upgrade_tank(self, request, pk=None):
        tank = self.get_object()

        if tank.is_in_battle:
            return Response(
                {"error": "Танк в бою"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not tank.can_upgrade():
            return Response(
                {"error": "Нельзя улучшить (макс. уровень или танк в бою)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        next_level = Level.objects.filter(
            level_number=tank.level.level_number + 1
        ).first()
        if not next_level:
            return Response(
                {"error": "Следующий уровень не найден"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cost = tank.level.upgrade_to_next_cost
        if cost is None:
            return Response(
                {"error": "Стоимость улучшения не определена"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            paid = Crewman.objects.filter(
                pk=tank.owner_id, credits__gte=cost
            ).update(credits=F("credits") - cost)
            if not paid:
                tank.owner.refresh_from_db(fields=["credits"])
                return Response(
                    {
                        "error": f"Не хватает кредитов. Нужно {cost}, у вас {tank.owner.credits}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            upgraded = Tank.objects.filter(
                pk=tank.pk, level_id=tank.level_id, is_in_battle=False
            ).update(level=next_level)
            if not upgraded:
                transaction.set_rollback(True)
                return Response(
                    {"error": "Нельзя улучшить (макс. уровень или танк в бою)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({"success": True, "new_level": next_level.level_number})

    @action(detail=True, methods=["POST"], url_path="sell")
    def sell_tank(self, request, pk=None):
        tank = self.get_object()
        if tank.is_in_battle:
            return Response(
                {"error": "Tank is in battle"}, status=status.HTTP_400_BAD_REQUEST
            )
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
        nation_popular = (
            Tank.objects.values("nation__name")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")
            .first()
        )
        stats["most_popular_nation"] = (
            nation_popular["nation__name"] if nation_popular else None
        )
        if stats["avg_level"] is None:
            stats["avg_level"] = 0
        return Response(stats)

    @action(detail=False, methods=["GET"], url_path="export-excel")
    def export_tanks_excel(self, request):
        tanks = self.get_queryset()
        owner_id = request.GET.get("owner")
        if owner_id:
            tanks = tanks.filter(owner_id=owner_id)

        wb = Workbook()
        ws = wb.active
        ws.title = "Танки"
        headers = [
            "ID",
            "Название",
            "Владелец",
            "Нация",
            "Уровень",
            "Урон/мин",
            "В бою",
            "Создан",
            "Фото в альбоме",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        for row, tank in enumerate(tanks, 2):
            ws.cell(row=row, column=1, value=tank.id)
            put_cell(ws, row, 2, tank.name)
            put_cell(ws, row, 3, tank.owner.user.username)
            put_cell(ws, row, 4, tank.nation.name)
            ws.cell(row=row, column=5, value=tank.level.level_number)
            ws.cell(row=row, column=6, value=tank.dpm)
            ws.cell(row=row, column=7, value="Да" if tank.is_in_battle else "Нет")
            ws.cell(
                row=row, column=8, value=tank.created_at.strftime("%Y-%m-%d %H:%M")
            )
            ws.cell(row=row, column=9, value=tank.photos.count())

        for column in ws.columns:
            max_length = 0
            col_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="tanks.xlsx"'
        return response


class TankPhotoViewSet(viewsets.ModelViewSet):
    serializer_class = TankPhotoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = TankPhoto.objects.select_related("tank__owner__user")
        if not user.is_superuser or not has_2fa(self.request):
            crewman, _ = Crewman.objects.get_or_create(user=user)
            return qs.filter(tank__owner=crewman)
        return qs.all()

    def perform_create(self, serializer):
        user = self.request.user
        tanks = Tank.objects.all()
        if not (user.is_superuser and has_2fa(self.request)):
            crewman, _ = Crewman.objects.get_or_create(user=user)
            tanks = tanks.filter(owner=crewman)
        try:
            tank = tanks.get(pk=self.request.data.get("tank"))
        except (Tank.DoesNotExist, ValueError, TypeError):
            raise NotFound("Tank not found")

        image = self.request.FILES.get("image")
        if image and image.size > MAX_UPLOAD_SIZE:
            raise DRFValidationError({"image": ["Файл слишком большой (максимум 5 МБ)"]})
        serializer.save(tank=tank)


class BattleRecordViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = BattleRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["result", "battle_level__level_number", "tank__name", "crewman", "tank"]

    def get_queryset(self):
        crewman, _ = Crewman.objects.get_or_create(user=self.request.user)
        qs = BattleRecord.objects.select_related(
            "tank__level", "crewman__user", "battle_level"
        )
        if self.request.user.is_superuser and has_2fa(self.request):
            return qs.order_by("-started_at")
        return qs.filter(crewman=crewman).order_by("-started_at")

    @action(detail=False, methods=["POST"], url_path="start")
    def start_battle(self, request):
        tank_id = request.data.get("tank_id")
        battle_level_id = request.data.get("battle_level_id")

        if not tank_id or not battle_level_id:
            return Response(
                {"error": "tank_id and battle_level_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        crewman, _ = Crewman.objects.get_or_create(user=self.request.user)
        try:
            tank = Tank.objects.get(id=tank_id, owner=crewman)
            battle_level = Level.objects.get(id=battle_level_id)
        except (Tank.DoesNotExist, Level.DoesNotExist, ValueError):
            return Response(
                {"error": "Invalid tank or level"}, status=status.HTTP_400_BAD_REQUEST
            )

        if tank.is_in_battle:
            return Response(
                {"error": "Tank already in battle"}, status=status.HTTP_400_BAD_REQUEST
            )

        tank_lvl = tank.level.level_number
        if battle_level.level_number not in [
            tank_lvl - 1,
            tank_lvl,
            tank_lvl + 1,
        ]:
            return Response(
                {"error": "Battle level not available for this tank"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            marked = Tank.objects.filter(
                pk=tank.pk, owner=crewman, is_in_battle=False
            ).update(is_in_battle=True)
            if not marked:
                return Response(
                    {"error": "Tank already in battle"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            battle_record = BattleRecord.objects.create(
                tank=tank,
                crewman=crewman,
                battle_level=battle_level,
                result="pending",
                reward_earned=0,
            )

        serializer = BattleRecordSerializer(battle_record)
        return Response(
            {"id": battle_record.id, "battle_duration": tank_lvl, **serializer.data},
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
        tank_level = battle.tank.level.level_number
        total_duration = tank_level
        remaining = max(0, total_duration - elapsed)

        return Response(
            {
                "remaining": math.ceil(remaining),
                "finished": False,
                "total_duration": total_duration,
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
        tank_level = battle.tank.level.level_number
        required_duration = tank_level

        if elapsed < required_duration:
            remaining = math.ceil(required_duration - elapsed)
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
        outcome = battle.process_battle_result(is_victory)
        if outcome is None:
            return Response(
                {"error": "Бой уже завершён"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BattleRecordSerializer(battle)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"], url_path="result")
    def battle_result(self, request, pk=None):
        battle = self.get_object()
        serializer = BattleRecordSerializer(battle)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"], url_path="stats")
    def battle_stats(self, request):
        crewman, _ = Crewman.objects.get_or_create(user=self.request.user)
        if self.request.user.is_superuser and has_2fa(self.request):
            queryset = BattleRecord.objects.all()
        else:
            queryset = BattleRecord.objects.filter(crewman=crewman)

        stats = queryset.aggregate(
            total_battles=Count("id"),
            victories=Count("id", filter=Q(result="victory")),
            defeats=Count("id", filter=Q(result="defeat")),
            total_reward=Sum("reward_earned"),
            avg_reward=Avg("reward_earned"),
        )
        stats["win_rate"] = (
            round(stats["victories"] / stats["total_battles"] * 100, 1)
            if stats["total_battles"]
            else 0
        )
        if stats["avg_reward"] is None:
            stats["avg_reward"] = 0
        return Response(stats)

    @action(detail=True, methods=["POST"], url_path="cancel")
    def cancel_battle(self, request, pk=None):
        battle = self.get_object()
        if battle.result != "pending":
            return Response(
                {"error": "Бой уже завершён"}, status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            updated = BattleRecord.objects.filter(pk=battle.pk, result="pending").update(
                result="defeat", reward_earned=0, finished_at=timezone.now()
            )
            if not updated:
                return Response(
                    {"error": "Бой уже завершён"}, status=status.HTTP_400_BAD_REQUEST
                )
            Tank.objects.filter(pk=battle.tank_id).update(is_in_battle=False)
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
            crewman, _ = Crewman.objects.get_or_create(user=request.user)
            data["credits"] = crewman.credits
            data["garage_slots"] = crewman.garage_slots
            data["second"] = has_2fa(request)
            data["crewman_id"] = crewman.id
        return Response(data)

    @action(detail=False, methods=["POST"], url_path="login")
    def login_user(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            clear_2fa(request)
            return Response({"success": True})
        return Response({"success": False}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=["POST"], url_path="logout")
    def logout_user(self, request):
        logout(request)
        return Response({"success": True})

    @action(detail=False, methods=["GET"], url_path="get-totp")
    def get_totp(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Not authenticated"}, status=401)
        if not request.user.is_staff:
            return Response({"error": "Forbidden"}, status=403)
        crewman, _ = Crewman.objects.get_or_create(user=request.user)
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
            return Response({"error": "Not authenticated"}, status=401)
        key = request.data.get("key")
        if not key:
            return Response({"error": "Key required"}, status=400)
        crewman, _ = Crewman.objects.get_or_create(user=request.user)
        if not crewman.totp_key:
            return Response({"error": "TOTP not set up"}, status=400)
        totp = pyotp.TOTP(crewman.totp_key)
        if totp.verify(str(key), valid_window=1):
            if not crewman.totp_confirmed:
                crewman.totp_confirmed = True
                crewman.save(update_fields=["totp_confirmed"])
            set_2fa(request)
            return Response({"success": True})
        return Response({"success": False}, status=400)

    @action(detail=False, methods=["POST"], url_path="logout-2fa")
    def logout_2fa(self, request):
        if request.user.is_authenticated:
            clear_2fa(request)
        return Response({"success": True})

    @action(
        detail=False,
        methods=["GET"],
        url_path="export-all-stats",
        permission_classes=[IsStaffAnd2FAVerified],
    )
    def export_all_stats(self, request):
        wb = Workbook()

        # Танки
        ws_tanks = wb.active
        ws_tanks.title = "Танки"
        tanks = Tank.objects.select_related("owner__user", "nation", "level").all()
        headers_tanks = [
            "ID",
            "Название",
            "Владелец",
            "Нация",
            "Уровень",
            "Урон/мин",
            "В бою",
            "Создан",
        ]
        for col, header in enumerate(headers_tanks, 1):
            cell = ws_tanks.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for row, tank in enumerate(tanks, 2):
            ws_tanks.cell(row=row, column=1, value=tank.id)
            put_cell(ws_tanks, row, 2, tank.name)
            put_cell(ws_tanks, row, 3, tank.owner.user.username)
            put_cell(ws_tanks, row, 4, tank.nation.name)
            ws_tanks.cell(row=row, column=5, value=tank.level.level_number)
            ws_tanks.cell(row=row, column=6, value=tank.dpm)
            ws_tanks.cell(row=row, column=7, value="Да" if tank.is_in_battle else "Нет")
            ws_tanks.cell(
                row=row, column=8, value=tank.created_at.strftime("%Y-%m-%d %H:%M")
            )

        # Бои
        ws_battles = wb.create_sheet("Бои")
        battles = BattleRecord.objects.select_related(
            "tank", "crewman__user", "battle_level"
        ).all()
        headers_battles = [
            "ID",
            "Танк",
            "Игрок",
            "Уровень боя",
            "Результат",
            "Награда",
            "Начало",
            "Завершение",
        ]
        for col, header in enumerate(headers_battles, 1):
            cell = ws_battles.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for row, battle in enumerate(battles, 2):
            ws_battles.cell(row=row, column=1, value=battle.id)
            put_cell(ws_battles, row, 2, battle.tank.name)
            put_cell(ws_battles, row, 3, battle.crewman.user.username)
            ws_battles.cell(row=row, column=4, value=battle.battle_level.level_number)
            result_text = "Ожидание"
            if battle.result == "victory":
                result_text = "Победа"
            elif battle.result == "defeat":
                result_text = "Поражение"
            ws_battles.cell(row=row, column=5, value=result_text)
            ws_battles.cell(row=row, column=6, value=battle.reward_earned)
            ws_battles.cell(
                row=row,
                column=7,
                value=battle.started_at.strftime("%Y-%m-%d %H:%M"),
            )
            ws_battles.cell(
                row=row,
                column=8,
                value=(
                    battle.finished_at.strftime("%Y-%m-%d %H:%M")
                    if battle.finished_at
                    else "-"
                ),
            )

        # Игроки
        ws_players = wb.create_sheet("Игроки")
        crewmen = Crewman.objects.select_related("user").annotate(
            tanks_count=Count("tanks")
        )
        headers_players = [
            "ID",
            "Имя",
            "Кредиты",
            "Слоты",
            "Танков",
            "Дата регистрации",
        ]
        for col, header in enumerate(headers_players, 1):
            cell = ws_players.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for row, crew in enumerate(crewmen, 2):
            ws_players.cell(row=row, column=1, value=crew.id)
            put_cell(ws_players, row, 2, crew.user.username)
            ws_players.cell(row=row, column=3, value=crew.credits)
            ws_players.cell(row=row, column=4, value=crew.garage_slots)
            ws_players.cell(row=row, column=5, value=crew.tanks_count)
            ws_players.cell(
                row=row, column=6, value=crew.created_at.strftime("%Y-%m-%d %H:%M")
            )

        # Нации
        ws_nations = wb.create_sheet("Нации")
        nations = Nation.objects.annotate(tanks_count=Count("tanks"))
        headers_nations = ["ID", "Название", "Количество танков"]
        for col, header in enumerate(headers_nations, 1):
            cell = ws_nations.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for row, nation in enumerate(nations, 2):
            ws_nations.cell(row=row, column=1, value=nation.id)
            put_cell(ws_nations, row, 2, nation.name)
            ws_nations.cell(row=row, column=3, value=nation.tanks_count)

        # Уровни
        ws_levels = wb.create_sheet("Уровни")
        levels = Level.objects.all()
        headers_levels = ["ID", "Уровень", "Стоимость создания", "Награда за бой"]
        for col, header in enumerate(headers_levels, 1):
            cell = ws_levels.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for row, level in enumerate(levels, 2):
            ws_levels.cell(row=row, column=1, value=level.id)
            ws_levels.cell(row=row, column=2, value=level.level_number)
            ws_levels.cell(row=row, column=3, value=level.creation_cost)
            ws_levels.cell(row=row, column=4, value=level.battle_reward)

        for ws in [ws_tanks, ws_battles, ws_players, ws_nations, ws_levels]:
            for column in ws.columns:
                max_length = 0
                col_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="full_statistics.xlsx"'
        return response