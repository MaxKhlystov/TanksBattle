<script setup>
import { onBeforeMount, ref, computed } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';
import Swal from 'sweetalert2';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { levels } = storeToRefs(tanksStore);

const newLevelNumber = ref(null);
const levelError = ref('');

onBeforeMount(async () => {
    await tanksStore.fetchLevels();
});

async function createLevel() {
    levelError.value = '';
    
    if (!newLevelNumber.value) {
        levelError.value = 'Введите номер уровня';
        return;
    }
    
    const maxLevel = Math.max(...levels.value.map(l => l.level_number), 0);
    if (newLevelNumber.value !== maxLevel + 1) {
        levelError.value = `Нельзя создать уровень ${newLevelNumber.value}. Следующий уровень должен быть ${maxLevel + 1}`;
        return;
    }
    
    if (levels.value.some(l => l.level_number === newLevelNumber.value)) {
        levelError.value = `Уровень ${newLevelNumber.value} уже существует`;
        return;
    }
    
    try {
        const createdLevelNumber = newLevelNumber.value;
        await tanksStore.createLevel({ level_number: createdLevelNumber });
        newLevelNumber.value = null;
        showSuccess('Уровень создан', `Уровень ${createdLevelNumber} успешно создан`);
    } catch (err) {
        levelError.value = err.response?.data?.level_number?.[0] || 'Ошибка создания уровня';
        showError('Ошибка', levelError.value);
    }
}

async function deleteLevel(id) {
    const level = levels.value.find(l => l.id === id);
    
    if (level.level_number !== maxLevelNumber.value) {
        showError('Ошибка', `Нельзя удалить уровень ${level.level_number}. Можно удалить только последний уровень (${maxLevelNumber.value}).`);
        return;
    }
    
    const result = await Swal.fire({
        title: 'Удалить уровень?',
        text: `Это удалит все танки ${level.level_number} уровня и вернёт владельцам полную стоимость (${level.creation_cost} кредитов за танк)!`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Да, удалить',
        cancelButtonText: 'Отмена',
        background: '#2c3e50',
        color: '#fff'
    });
    
    if (result.isConfirmed) {
        try {
            await tanksStore.deleteLevel(id);
            showSuccess('Уровень удалён', 'Уровень успешно удалён');
        } catch (err) {
            showError('Ошибка', err.response?.data?.error || 'Не удалось удалить уровень');
        }
    }
}

const maxLevelNumber = computed(() => {
    if (!levels.value.length) return 0;
    return Math.max(...levels.value.map(l => l.level_number));
});

</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated && userInfo.is_staff">
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
                        <small>Следующий уровень должен быть №{{ Math.max(...levels.map(l => l.level_number), 0) + 1 }}</small>
                        <small class="d-block mt-1">💰 Стоимость создания и награда рассчитываются автоматически</small>
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
                                    <button class="btn-custom-danger btn-sm" @click="deleteLevel(level.id)" 
                                    :disabled="level.level_number !== maxLevelNumber">🗑️</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div v-else-if="userInfo && userInfo.is_authenticated && userInfo.is_staff && !userInfo.second" class="alert-custom-warning">
            Для создания уровней рекомендуется двухфакторная аутентификация
        </div>
        <div v-else class="alert-custom-warning">Доступ только для администраторов</div>
    </div>
</template>

<style scoped>
.action-buttons {
    display: flex;
    gap: 8px;
}
</style>