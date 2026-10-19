<script setup>
import { onBeforeMount } from 'vue';
import { storeToRefs } from 'pinia';
import { useTanksStore } from '@/stores/tanks_store';

const tanksStore = useTanksStore();
const { allCrewmen } = storeToRefs(tanksStore);

onBeforeMount(async () => {
    await tanksStore.fetchAllCrewmen();
});

async function onSaveClick(crewman) {
    try {
        await tanksStore.updateCrewman(crewman);
        alert('Сохранено');
    } catch (error) {
        alert(error.response.data.error);
    }
}
</script>

<template>
    <div class="card">
        <div class="card-header">Пользователи</div>
        <div class="card-body">
            <table class="table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Кредиты</th>
                        <th>Мест в ангаре</th>
                        <th>Танков</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="c in allCrewmen" :key="c.id">
                        <td>{{ c.id }}</td>
                        <td>{{ c.username }}</td>
                        <td><input type="number" class="form-control" v-model.number="c.credits"></td>
                        <td><input type="number" class="form-control" v-model.number="c.garage_slots"></td>
                        <td>{{ c.tanks_count }}</td>
                        <td><button class="btn btn-primary btn-sm" @click="onSaveClick(c)">Сохранить</button></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>
