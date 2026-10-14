<script setup>
import { onBeforeMount, ref, computed } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError, getErrorMessage } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { nations, levels, myTanks } = storeToRefs(tanksStore);

const newTank = ref({ name: '', nation: null, level: null });
const pictureFile = ref(null);
const picturePreview = ref(null);
const isCreating = ref(false);

// Пользователя проверяет router.beforeEach; здесь только данные для формы
onBeforeMount(async () => {
    await tanksStore.fetchNations();
    await tanksStore.fetchLevels();
    await tanksStore.fetchMyTanks();
});

const selectedLevelCost = computed(() => {
    const level = tanksStore.getLevelInfo(newTank.value.level);
    return level ? level.creation_cost : 0;
});

function onPictureChange(event) {
    const file = event.target.files[0];
    pictureFile.value = file || null;
    picturePreview.value = file ? URL.createObjectURL(file) : null;
}

function validationError() {
    if (!newTank.value.name.trim()) return 'Введите название танка';
    if (!newTank.value.nation) return 'Выберите нацию';
    if (!newTank.value.level) return 'Выберите уровень';
    if (userInfo.value.credits < selectedLevelCost.value) {
        return `Недостаточно кредитов! Нужно: ${selectedLevelCost.value}, у вас: ${userInfo.value.credits}`;
    }
    if (myTanks.value.length >= userInfo.value.garage_slots) return 'Нет свободных мест в ангаре!';
    return null;
}

async function onCreateTank() {
    if (isCreating.value) return;
    const error = validationError();
    if (error) {
        showError('Ошибка', error);
        return;
    }

    const formData = new FormData();
    formData.append('name', newTank.value.name);
    formData.append('nation', newTank.value.nation);
    formData.append('level', newTank.value.level);
    if (pictureFile.value) {
        formData.append('picture', pictureFile.value);
    }

    isCreating.value = true;
    try {
        await tanksStore.createTank(formData);
        newTank.value = { name: '', nation: null, level: null };
        pictureFile.value = null;
        picturePreview.value = null;
        showSuccess('Успех!', 'Танк успешно создан');
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Ошибка при создании танка'));
    } finally {
        isCreating.value = false;
    }
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_authenticated">
            <div class="custom-card">
                <div class="custom-card-header">Создать новый танк</div>
                <div class="custom-card-body">
                    <form @submit.prevent="onCreateTank">
                        <div class="form-group">
                            <label>Название танка</label>
                            <input type="text" class="custom-form-control" v-model="newTank.name" placeholder="Например: Т-34" required>
                        </div>
                        <div class="form-group">
                            <label>Нация</label>
                            <select class="custom-form-select" v-model="newTank.nation" required>
                                <option :value="null" disabled>Выберите нацию</option>
                                <option :value="nation.id" v-for="nation in nations" :key="nation.id">
                                    {{ nation.name }}
                                </option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Уровень</label>
                            <select class="custom-form-select" v-model="newTank.level" required>
                                <option :value="null" disabled>Выберите уровень</option>
                                <option :value="level.id" v-for="level in levels" :key="level.id">
                                    {{ level.level_number }} уровень ({{ level.creation_cost }} кредитов)
                                </option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Изображение танка</label>
                            <input type="file" class="custom-form-control" @change="onPictureChange" accept="image/*">
                            <img v-if="picturePreview" :src="picturePreview" style="max-width: 200px; margin-top: 10px; border-radius: 10px;">
                        </div>
                        <div v-if="selectedLevelCost > 0" class="alert-custom-info">
                            <strong>Стоимость создания:</strong> {{ selectedLevelCost }} кредитов<br>
                            <strong>Доступно кредитов:</strong> {{ userInfo.credits }}
                        </div>
                        <button type="submit" class="btn-custom-danger w-100" :disabled="isCreating">
                            {{ isCreating ? 'Создание...' : 'Создать танк' }}
                        </button>
                    </form>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Пожалуйста, авторизуйтесь</div>
    </div>
</template>