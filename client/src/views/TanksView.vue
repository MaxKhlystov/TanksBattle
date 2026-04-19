<script setup>
import { onBeforeMount, ref, watch } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { nations, levels, myTanks } = storeToRefs(tanksStore);

const newTank = ref({ name: '', nation: null, level: null });
const pictureFile = ref(null);
const picturePreview = ref(null);
const errorMessage = ref('');
const showErrorModal = ref(false);
const selectedLevelCost = ref(0);

onBeforeMount(async () => {
    await tanksStore.fetchNations();
    await tanksStore.fetchLevels();
    await tanksStore.fetchMyTanks();
});

function updateLevelCost() {
    if (newTank.value.level) {
        const level = tanksStore.getLevelInfo(newTank.value.level);
        selectedLevelCost.value = level ? level.creation_cost : 0;
    } else {
        selectedLevelCost.value = 0;
    }
}

watch(() => newTank.value.level, () => updateLevelCost());

function onPictureChange(event) {
    const file = event.target.files[0];
    if (file) {
        pictureFile.value = file;
        picturePreview.value = URL.createObjectURL(file);
    } else {
        pictureFile.value = null;
        picturePreview.value = null;
    }
}

async function onCreateTank() {
    if (!newTank.value.name.trim()) {
        errorMessage.value = 'Введите название танка';
        showErrorModal.value = true;
        return;
    }
    if (!newTank.value.nation) {
        errorMessage.value = 'Выберите нацию';
        showErrorModal.value = true;
        return;
    }
    if (!newTank.value.level) {
        errorMessage.value = 'Выберите уровень';
        showErrorModal.value = true;
        return;
    }
    if (userInfo.value.credits < selectedLevelCost.value) {
        errorMessage.value = `Недостаточно кредитов! Нужно: ${selectedLevelCost.value}, у вас: ${userInfo.value.credits}`;
        showErrorModal.value = true;
        return;
    }
    if (myTanks.value.length >= userInfo.value.garage_slots) {
        errorMessage.value = 'Нет свободных мест в ангаре!';
        showErrorModal.value = true;
        return;
    }

    const formData = new FormData();
    formData.append('name', newTank.value.name);
    formData.append('nation', newTank.value.nation);
    formData.append('level', newTank.value.level);
    if (pictureFile.value) {
        formData.append('picture', pictureFile.value);
    }

    try {
        await tanksStore.createTank(formData);
        newTank.value = { name: '', nation: null, level: null };
        pictureFile.value = null;
        picturePreview.value = null;
        selectedLevelCost.value = 0;
        showSuccess('Успех!', 'Танк успешно создан');
    } catch (error) {
        showError('Ошибка', error.response?.data?.error || 'Ошибка при создании танка');
    }
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated">
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
                        <button type="submit" class="btn-custom-danger w-100">Создать танк</button>
                    </form>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Пожалуйста, авторизуйтесь</div>
    </div>

    <!-- Модалка ошибки -->
    <div v-if="showErrorModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Ошибка</h5>
                    <button class="close-btn" @click="showErrorModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    {{ errorMessage }}
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showErrorModal = false">Закрыть</button>
                </div>
            </div>
        </div>
    </div>
</template>