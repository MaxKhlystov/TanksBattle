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
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    def __str__(self):
        return f"{self.level_number} уровень"

    @property
    def creation_cost(self):
        n = self.level_number
        return 1000 * (n * (n + 1) // 2)

    @property
    def upgrade_to_next_cost(self):
        next_level = Level.objects.filter(level_number=self.level_number + 1).first()
        if next_level:
            return next_level.creation_cost // 2
        return None

    @property
    def battle_reward(self):
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
        return self.user.username

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
        return self.name

    @property
    def dpm(self):
        return 100 + (self.level.level_number - 1) * 50

    @property
    def upgrade_cost(self):
        return self.level.upgrade_to_next_cost

    @property
    def sell_price(self):
        return self.level.creation_cost // 2

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
    battle_level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name='battles')
    result = models.CharField("Результат", max_length=20, choices=RESULT_CHOICES, default='pending')
    reward_earned = models.BigIntegerField("Полученная награда", default=0)
    started_at = models.DateTimeField("Время начала", auto_now_add=True)
    finished_at = models.DateTimeField("Время завершения", null=True, blank=True)

    def __str__(self):
        return f"{self.tank.name} - {self.get_result_display()}"

    class Meta:
        verbose_name = "Запись о сражении"
        verbose_name_plural = "Записи о сражениях"
        ordering = ['-started_at']
