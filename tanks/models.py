from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

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
        validators=[MinValueValidator(1), MaxValueValidator(100)])

    def __str__(self):
        return f"{self.level_number} уровень"

    @property
    def creation_cost(self):
        """Стоимость создания танка этого уровня"""
        if not self.level_number:
            return 0
        n = self.level_number
        return 1000 * (n * (n + 1) // 2)

    @property
    def upgrade_to_next_cost(self):
        """Стоимость повышения с этого уровня на следующий"""
        if not self.level_number:
            return None
        next_level = Level.objects.filter(level_number=self.level_number + 1).first()
        if next_level:
            return next_level.creation_cost // 2
        return None

    @property
    def upgrade_cost(self):
        """Стоимость улучшения до следующего уровня (половина стоимости создания следующего уровня)"""
        next_level = Level.objects.filter(level_number=self.level_number + 1).first()
        if next_level:
            return next_level.creation_cost // 2
        return None

    @property
    def battle_reward(self):
        """Награда за бой на этом уровне"""
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
    totp_key = models.CharField(max_length=128, null=True, blank=True)  # для 2FA

    def __str__(self):
        return f"{self.user.username} (Кредитов: {self.credits})"

    def can_afford(self, amount):
        return self.credits >= amount

    def deduct_credits(self, amount):
        if self.can_afford(amount):
            self.credits -= amount
            self.save()
            return True
        return False

    def add_credits(self, amount):
        self.credits += amount
        self.save()

    def available_garage_slots(self):
        return self.garage_slots - self.tanks.count()

    class Meta:
        verbose_name = "Член экипажа"
        verbose_name_plural = "Члены экипажа"


class Tank(models.Model):
    name = models.CharField("Название танка", max_length=100)
    owner = models.ForeignKey(Crewman, on_delete=models.CASCADE, related_name='tanks')
    nation = models.ForeignKey(Nation, on_delete=models.CASCADE, related_name='tanks')
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='tanks')
    is_in_battle = models.BooleanField("В бою", default=False)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    picture = models.ImageField("Изображение танка", upload_to="images/tanks/", null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.nation}) - {self.level}"

    @property
    def dpm(self):
        return 100 + (self.level.level_number - 1) * 50

    @property
    def upgrade_cost(self):
        next_level = Level.objects.filter(level_number=self.level.level_number + 1).first()
        if next_level:
            return next_level.upgrade_cost
        return None

    def can_upgrade(self):
        next_level = Level.objects.filter(level_number=self.level.level_number + 1).first()
        return next_level is not None and not self.is_in_battle

    def upgrade(self):
        if not self.can_upgrade():
            return False
        next_level = Level.objects.filter(level_number=self.level.level_number + 1).first()
        cost = next_level.upgrade_cost
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
        self.owner.add_credits(self.sell_price)
        self.delete()
        return True

    class Meta:
        verbose_name = "Танк"
        verbose_name_plural = "Танки"
        ordering = ['-created_at']


class BattleRecord(models.Model):
    RESULT_CHOICES = [
        ('pending', 'Ожидание'),
        ('victory', 'Победа'),
        ('defeat', 'Поражение'),
    ]

    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='battles')
    crewman = models.ForeignKey(Crewman, on_delete=models.CASCADE, related_name='battles')
    battle_level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='battles')
    result = models.CharField("Результат", max_length=20, choices=RESULT_CHOICES, default='pending')
    reward_earned = models.BigIntegerField("Полученная награда", default=0)
    started_at = models.DateTimeField("Время начала", auto_now_add=True)
    finished_at = models.DateTimeField("Время завершения", null=True, blank=True)

    def __str__(self):
        return f"{self.tank.name} - {self.get_result_display()} на {self.battle_level}"

    def process_battle_result(self, is_victory):
        from django.utils import timezone
        if is_victory:
            self.result = 'victory'
            self.reward_earned = self.battle_level.battle_reward
            self.crewman.add_credits(self.reward_earned)
        else:
            self.result = 'defeat'
            self.reward_earned = 0
        self.finished_at = timezone.now()
        self.save()
        self.tank.is_in_battle = False
        self.tank.save()
        return self.result == 'victory'

    class Meta:
        verbose_name = "Запись о сражении"
        verbose_name_plural = "Записи о сражениях"
        ordering = ['-started_at']