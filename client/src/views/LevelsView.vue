<script setup>
import { onBeforeMount, ref, computed } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError, showConfirm, getErrorMessage } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { levels } = storeToRefs(tanksStore);

const newLevelNumber = ref(null);
const levelError = ref('');

const maxLevelNumber = computed(() => Math.max(0, ...levels.value.map(l => l.level_number)));

onBeforeMount(async () => {
    await tanksStore.fetchLevels();
});

// Правило «только следующий по порядку» проверяет и сервер; здесь — для быстрой подсказки
async function createLevel() {
    levelError.value = '';
    if (!newLevelNumber.value) {
        levelError.value = 'Введите номер уровня';
        return;
    }
    if (newLevelNumber.value !== maxLevelNumber.value + 1) {
        levelError.value = `Нельзя создать уровень ${newLevelNumber.value}. Следующий уровень должен быть ${maxLevelNumber.value + 1}`;
        return;
    }
    try {
        const createdLevelNumber = newLevelNumber.value;
        await tanksStore.createLevel({ level_number: createdLevelNumber });
        newLevelNumber.value = null;
        showSuccess('Уровень создан', `Уровень ${createdLevelNumber} успешно создан`);
    } catch (err) {
        levelError.value = getErrorMessage(err, 'Ошибка создания уровня');
    }
}

// Кнопка удаления активна только у последнего уровня (то же правило на сервере)
async function deleteLevel(level) {
    const confirmed = await showConfirm(
        'Удалить уровень?',
        `Это удалит все танки ${level.level_number} уровня и вернёт владельцам полную стоимость (${level.creation_cost} кредитов за танк). Активные бои на этом уровне будут отменены, а история боёв этого уровня удалена!`
    );
    if (!confirmed) return;
    try {
        await tanksStore.deleteLevel(level.id);
        await tanksStore.fetchMyTanks();
        await userStore.checkLogin();
        showSuccess('Уровень удалён', 'Уровень успешно удалён');
    } catch (err) {
        showError('Ошибка', getErrorMessage(err, 'Не удалось удалить уровень'));
    }
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_authenticated && userInfo.is_staff">
            <div class="custom-card mb-4">
                <div class="custom-card-header bg-danger">Управление уровнями</div>
                <div class="custom-card-body" v-if="userInfo.is_staff && userInfo.second">
                    <h5>Добавить уровень</h5>
                    <div v-if="levelError" class="alert-custom-danger">{{ levelError }}</div>
                    <div class="row">
                        <div class="col-md-8">
                            <input type="number" class="custom-form-control" v-model="newLevelNumber" placeholder="Номер уровня">
                        </div>
                        <div class="col-md-4">
                            <button class="btn-custom-success w-100" @click="createLevel">Добавить уровень</button>
                        </div>
                    </div>
                    <div class="alert-custom-info mt-2">
                        <small>Следующий уровень должен быть №{{ maxLevelNumber + 1 }}</small>
                        <small class="d-block mt-1">💰 Стоимость создания и награда рассчитываются автоматически</small>
                    </div>
                </div>
                <div class="custom-card-body" v-else>
                    <div class="alert-custom-warning mb-0">
                        Для создания и удаления уровней требуется двухфакторная аутентификация
                    </div>
                </div>
            </div>

            <div class="custom-card">
                <div class="custom-card-header bg-success">Список уровней</div>
                <div class="custom-card-body p-0">
                    <table class="custom-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Уровень</th>
                                <th>Стоимость создания</th>
                                <th>Награда за бой</th>
                                <th v-if="userInfo.second">Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="level in levels" :key="level.id">
                                <td>{{ level.id }}</td>
                                <td><strong>{{ level.level_number }}</strong></td>
                                <td>{{ level.creation_cost }} 💰</td>
                                <td>{{ level.battle_reward }} 💰</td>
                                <td v-if="userInfo.second" class="action-buttons">
                                    <button class="btn-custom-danger btn-sm" @click="deleteLevel(level)" 
                                    :disabled="level.level_number !== maxLevelNumber">🗑️</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Доступ только для администраторов</div>
    </div>
</template>