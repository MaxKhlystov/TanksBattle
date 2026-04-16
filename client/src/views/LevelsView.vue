<script setup>
import { onBeforeMount, ref } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { levels } = storeToRefs(tanksStore);

const newLevelNumber = ref(null);
const editLevel = ref(null);
const showEditModal = ref(false);
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
        await tanksStore.createLevel({ level_number: newLevelNumber.value });
        newLevelNumber.value = null;
        levelError.value = '';
        showSuccess('Уровень создан', `Уровень ${newLevelNumber.value} успешно создан`);
    } catch (err) {
        levelError.value = err.response?.data?.level_number?.[0] || 'Ошибка создания уровня';
        showError('Ошибка', levelError.value);
    }
}

async function updateLevel() {
    if (editLevel.value) {
        try {
            await tanksStore.updateLevel(editLevel.value.id, {
                level_number: editLevel.value.level_number
            });
            showEditModal.value = false;
            editLevel.value = null;
            showSuccess('Уровень обновлён', `Уровень обновлён до ${editLevel.value.level_number}`);
        } catch (err) {
            showError('Ошибка', 'Не удалось обновить уровень');
        }
    }
}

async function deleteLevel(id) {
    const result = await Swal.fire({
        title: 'Удалить уровень?',
        text: 'Это также удалит все связанные танки!',
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
            showError('Ошибка', 'Не удалось удалить уровень');
        }
    }
}

function openEditModal(level) {
    editLevel.value = { ...level };
    showEditModal.value = true;
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated && userInfo.is_staff">
            <div class="custom-card mb-4">
                <div class="custom-card-header bg-danger">Управление уровнями</div>
                <div class="custom-card-body">
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
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="level in levels" :key="level.id">
                                <td>{{ level.id }}</td>
                                <td><strong>{{ level.level_number }}</strong></td>
                                <td>{{ level.creation_cost }} 💰</td>
                                <td>{{ level.battle_reward }} 💰</td>
                                <td class="action-buttons">
                                    <button class="btn-custom-warning btn-sm" @click="openEditModal(level)">✏️</button>
                                    <button class="btn-custom-danger btn-sm" @click="deleteLevel(level.id)">🗑️</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div v-else-if="userInfo && userInfo.is_authenticated && userInfo.is_staff && !userInfo.second" class="alert-custom-warning">
            Для создания/редактирования уровней рекомендуется двухфакторная аутентификация
        </div>
        <div v-else class="alert-custom-warning">Доступ только для администраторов</div>
    </div>

    <!-- Модалка редактирования -->
    <div v-if="showEditModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Редактировать уровень</h5>
                    <button class="close-btn" @click="showEditModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <div class="form-group">
                        <label>Номер уровня</label>
                        <input type="number" class="custom-form-control" v-model="editLevel.level_number">
                    </div>
                    <div class="alert-custom-info mt-2">
                        <small>⚠️ Изменение номера уровня повлияет на стоимость создания и награду!</small>
                    </div>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showEditModal = false">Отмена</button>
                    <button class="btn-custom-primary" @click="updateLevel">Сохранить</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.action-buttons {
    display: flex;
    gap: 8px;
}
</style>