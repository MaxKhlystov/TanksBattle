<script setup>
import { ref, onBeforeMount } from 'vue';
import axios from 'axios';
import { useUserStore } from '@/stores/user_store';
import { storeToRefs } from 'pinia';

const userStore = useUserStore();
const { userInfo } = storeToRefs(userStore);
const crewmen = ref([]);
const loading = ref(false);
const message = ref('');

onBeforeMount(async () => {
    if (userInfo.value.is_staff && userInfo.value.second) {
        await loadCrewmen();
    }
});

async function loadCrewmen() {
    loading.value = true;
    try {
        const response = await axios.get('/api/crewman/list-users/');
        crewmen.value = response.data;
    } catch (error) {
        console.error('Ошибка загрузки пользователей:', error);
        message.value = 'Ошибка загрузки';
    }
}

async function updateCrewman(crewman) {
    try {
        await axios.put(`/api/crewman/${crewman.id}/`, {
            credits: crewman.credits,
            garage_slots: crewman.garage_slots
        });
        message.value = `Пользователь ${crewman.username} обновлён`;
        setTimeout(() => { message.value = ''; }, 3000);
    } catch (error) {
        console.error('Ошибка обновления:', error);
        message.value = 'Ошибка при обновлении';
    }
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_staff && userInfo.second">
            <div class="custom-card">
                <div class="custom-card-header bg-danger">Управление пользователями</div>
                <div class="custom-card-body">
                    <div v-if="message" class="alert-custom-success">{{ message }}</div>
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
                            <tr v-for="c in crewmen" :key="c.id">
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