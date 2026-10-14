<script setup>
import { ref, onBeforeMount } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from 'pinia';
import { showSuccess, showError, getErrorMessage } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { allCrewmen } = storeToRefs(tanksStore);
const loading = ref(false);

// Доступ проверяет роутер (requiresStaff + requires2FA)
onBeforeMount(async () => {
    loading.value = true;
    await tanksStore.fetchAllCrewmen();
    loading.value = false;
});

async function updateCrewman(crewman) {
    try {
        await tanksStore.updateCrewman(crewman);
        showSuccess('Сохранено', `Пользователь ${crewman.username} обновлён`);
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Ошибка при обновлении'));
    }
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_staff && userInfo.second">
            <div class="custom-card">
                <div class="custom-card-header bg-danger">Управление пользователями</div>
                <div class="custom-card-body">
                    <div v-if="loading" class="text-center">Загрузка...</div>
                    <table class="custom-table" v-else>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Имя пользователя</th>
                                <th>Кредиты</th>
                                <th>Мест в ангаре</th>
                                <th>Танков</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="c in allCrewmen" :key="c.id">
                                <td>{{ c.id }}</td>
                                <td>{{ c.username }}</td>
                                <td>
                                    <input type="number" class="custom-form-control" v-model.number="c.credits" style="width: 120px;">
                                </td>
                                <td>
                                    <input type="number" class="custom-form-control" v-model.number="c.garage_slots" style="width: 80px;">
                                </td>
                                <td>{{ c.tanks_count }}</td>
                                <td>
                                    <button class="btn-custom-primary btn-sm" @click="updateCrewman(c)">Сохранить</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div v-else-if="userInfo.is_staff && !userInfo.second" class="alert-custom-warning">
            Для доступа к управлению пользователями требуется двухфакторная аутентификация
        </div>
        <div v-else class="alert-custom-warning">
            Доступ только для администраторов
        </div>
    </div>
</template>