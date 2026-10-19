<script setup>
import { onBeforeMount, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { levels } = storeToRefs(tanksStore);

const newLevelNumber = ref(null);

onBeforeMount(async () => {
    await tanksStore.fetchLevels();
});

async function onLevelAdd() {
    try {
        await tanksStore.createLevel({ level_number: newLevelNumber.value });
        newLevelNumber.value = null;
    } catch (error) {
        alert(error.response.data.error);
    }
}

async function onRemoveClick(level) {
    if (!confirm(`Удалить уровень ${level.level_number}? Все танки этого уровня будут удалены, владельцам вернётся их стоимость.`)) {
        return;
    }
    try {
        await tanksStore.deleteLevel(level.id);
        await userStore.checkLogin();
    } catch (error) {
        alert(error.response.data.error);
    }
}
</script>

<template>
    <div class="card mb-3" v-if="userInfo.second">
        <div class="card-header">Добавить уровень</div>
        <div class="card-body">
            <form @submit.prevent.stop="onLevelAdd" class="row">
                <div class="col">
                    <input type="number" class="form-control" v-model="newLevelNumber" placeholder="Номер уровня" required>
                </div>
                <div class="col-auto">
                    <button type="submit" class="btn btn-success">Добавить</button>
                </div>
            </form>
        </div>
    </div>
    <div class="alert alert-warning" v-else>Для изменения уровней нужна двухфакторная аутентификация</div>

    <div class="card">
        <div class="card-header">Уровни</div>
        <div class="card-body">
            <table class="table">
                <thead>
                    <tr>
                        <th>Уровень</th>
                        <th>Стоимость создания</th>
                        <th>Награда за бой</th>
                        <th v-if="userInfo.second"></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="level in levels" :key="level.id">
                        <td>{{ level.level_number }}</td>
                        <td>{{ level.creation_cost }}</td>
                        <td>{{ level.battle_reward }}</td>
                        <td v-if="userInfo.second">
                            <button class="btn btn-danger btn-sm" @click="onRemoveClick(level)">Удалить</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>
