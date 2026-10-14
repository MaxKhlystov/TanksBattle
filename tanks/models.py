# tanks/models.py

from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Nation(models.Model):
    name = models.CharField("Название нации", max_length=50, unique=True)
    flag = models.ImageField("Флаг", upload_to="images/flags/", null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Нация"
        verbose_name_plural = "Нации"
        ordering = ['name']

class Level(models.Model):
    level_number = models.IntegerField(
        "Номер уровня",
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    def __str__(self):
        return f"{self.level_number} уровень"

    @property
    def creation_cost(self):
        if not self.level_number:
            return 0
        n = self.level_number
        return 1000 * (n * (n + 1) // 2)

    @property
    def upgrade_to_next_cost(self):
        if not self.level_number:
            return None
        next_level = Level.objects.filter(level_number=self.level_number + 1).first()
        if next_level:
            return next_level.creation_cost // 2
        return None

    @property
    def battle_reward(self):
        if not self.level_number:
            return 0
        return (100 + 25 * self.level_number) * self.level_number

    class Meta:
        verbose_name = "Уровень"
        verbose_name_plural = "Уровни"
        ordering = ['level_number']

class Crewman(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='crewman')
    credits = models.BigIntegerField("Кредиты", default=1000)
    garage_slots = models.IntegerField("Мест в ангаре", default=3)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    totp_key = models.CharField(max_length=128, null=True, blank=True)
    totp_confirmed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} (Кредитов: {self.credits})"

    def can_afford(self, amount):
        return self.credits >= amount

    def deduct_credits(self, amount):
        updated = Crewman.objects.filter(pk=self.pk, credits__gte=amount).update(
            credits=F('credits') - amount
        )
        if updated:
            self.refresh_from_db(fields=['credits'])
            return True
        return False

    def add_credits(self, amount):
        Crewman.objects.filter(pk=self.pk).update(credits=F('credits') + amount)
        self.refresh_from_db(fields=['credits'])

    def available_garage_slots(self):
        return self.garage_slots - self.tanks.count()

    class Meta:
        verbose_name = "Член экипажа"
        verbose_name_plural = "Члены экипажа"

class Tank(models.Model):
    name = models.CharField("Название танка", max_length=100)
    owner = models.ForeignKey(Crewman, on_delete=models.CASCADE, related_name='tanks')
    nation = models.ForeignKey(Nation, on_delete=models.PROTECT, related_name='tanks')
    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name='tanks')
    is_in_battle = models.BooleanField("В бою", default=False)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    picture = models.ImageField("Основное изображение", upload_to="images/tanks/", null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.nation}) - {self.level}"

    @property
    def dpm(self):
        return 100 + (self.level.level_number - 1) * 50

    @property
    def upgrade_cost(self):
        return self.level.upgrade_to_next_cost

    def can_upgrade(self):
        next_level = Level.objects.filter(level_number=self.level.level_number + 1).first()
        return next_level is not None and not self.is_in_battle

    def upgrade(self):
        if not self.can_upgrade():
            return False
        next_level = Level.objects.filter(level_number=self.level.level_number + 1).first()
        cost = self.level.upgrade_to_next_cost
        if self.owner.deduct_credits(cost):
            self.level = next_level
            self.save()
            return True
        return False

    @property
    def sell_price(self):
        return self.level.creation_cost // 2

    def sell(self):
        if self.is_in_battle:
            return False
        price = self.sell_price
        with transaction.atomic():
            deleted, _ = Tank.objects.filter(
                pk=self.pk, owner_id=self.owner_id, is_in_battle=False
            ).delete()
            if not deleted:
                return False
            Crewman.objects.filter(pk=self.owner_id).update(credits=F('credits') + price)
        return True

    class Meta:
        verbose_name = "Танк"
        verbose_name_plural = "Танки"
        ordering = ['-created_at']

class TankPhoto(models.Model):
    """Модель для альбома фотографий танка"""
    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Фотография", upload_to="images/tanks/gallery/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фотография танка"
        verbose_name_plural = "Фотографии танков"

class BattleRecord(models.Model):
    RESULT_CHOICES = [
        ('pending', 'Ожидание'),
        ('victory', 'Победа'),
        ('defeat', 'Поражение'),
    ]
    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='battles')
    crewman = models.ForeignKey(Crewman, on_delete=models.CASCADE, related_name='battles')
    battle_level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name='battles')
    result = models.CharField("Результат", max_length=20, choices=RESULT_CHOICES, default='pending')
    reward_earned = models.BigIntegerField("Полученная награда", default=0)
    started_at = models.DateTimeField("Время начала", auto_now_add=True)
    finished_at = models.DateTimeField("Время завершения", null=True, blank=True)

    def __str__(self):
        return f"{self.tank.name} - {self.get_result_display()} на {self.battle_level}"

    def process_battle_result(self, is_victory):
        """
        Возвращает True/False (победа/поражение) или None, если бой уже был обработан.
        Результат фиксируется атомарно: награда начисляется ровно один раз.
        """
        reward = self.battle_level.battle_reward if is_victory else 0
        now = timezone.now()
        with transaction.atomic():
            updated = BattleRecord.objects.filter(pk=self.pk, result='pending').update(
                result='victory' if is_victory else 'defeat',
                reward_earned=reward,
                finished_at=now,
            )
            if not updated:
                self.refresh_from_db()
                return None
            if reward:
                Crewman.objects.filter(pk=self.crewman_id).update(credits=F('credits') + reward)
            Tank.objects.filter(pk=self.tank_id).update(is_in_battle=False)
        self.result = 'victory' if is_victory else 'defeat'
        self.reward_earned = reward
        self.finished_at = now
        return is_victory

    class Meta:
        verbose_name = "Запись о сражении"
        verbose_name_plural = "Записи о сражениях"
        ordering = ['-started_at']