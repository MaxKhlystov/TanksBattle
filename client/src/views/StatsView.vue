<script setup>
import { onBeforeMount, ref } from 'vue';
import axios from 'axios';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';

const userStore = useUserStore();
const { userInfo } = storeToRefs(userStore);

const tankStats = ref({});
const battleStats = ref({});
const nationStats = ref({});
const levelStats = ref({ level_distribution: [] });

onBeforeMount(async () => {
    tankStats.value = (await axios.get('/api/tanks/stats/')).data;
    battleStats.value = (await axios.get('/api/battles/stats/')).data;
    nationStats.value = (await axios.get('/api/nations/stats/')).data;
    levelStats.value = (await axios.get('/api/levels/stats/')).data;
});

async function onExport() {
    const r = await axios.get('/api/user/export-all-stats/', { responseType: 'blob' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(r.data);
    link.download = 'full_statistics.xlsx';
    link.click();
}
</script>

<template>
    <div class="mb-3">
        <button class="btn btn-success" @click="onExport" :disabled="!userInfo.second">Экспорт статистики в Excel</button>
        <span class="text-white ms-2" v-if="!userInfo.second">Для экспорта нужна двухфакторная аутентификация</span>
    </div>

    <div class="card mb-3">
        <div class="card-header">Танки</div>
        <div class="card-body">
            <p class="mb-1">Всего танков: {{ tankStats.total_tanks }}</p>
            <p class="mb-1">Средний уровень: {{ tankStats.avg_level }}</p>
            <p class="mb-1">Максимальный уровень: {{ tankStats.max_level }}</p>
            <p class="mb-0">Минимальный уровень: {{ tankStats.min_level }}</p>
        </div>
    </div>

    <div class="card mb-3">
        <div class="card-header">Бои</div>
        <div class="card-body">
            <p class="mb-1">Всего боёв: {{ battleStats.total_battles }}</p>
            <p class="mb-1">Побед: {{ battleStats.victories }}</p>
            <p class="mb-1">Поражений: {{ battleStats.defeats }}</p>
            <p class="mb-1">Процент побед: {{ battleStats.win_rate }}%</p>
            <p class="mb-0">Всего заработано: {{ battleStats.total_reward }}</p>
        </div>
    </div>

    <div class="card mb-3">
        <div class="card-header">Нации</div>
        <div class="card-body">
            <p class="mb-1">Всего наций: {{ nationStats.total_nations }}</p>
            <p class="mb-1">Среднее количество танков на нацию: {{ nationStats.avg_tanks_per_nation }}</p>
            <p class="mb-0">Самая популярная нация: {{ nationStats.most_popular_nation }} ({{ nationStats.most_popular_tanks_count }} танков)</p>
        </div>
    </div>

    <div class="card mb-3">
        <div class="card-header">Уровни</div>
        <div class="card-body">
            <p>Всего уровней: {{ levelStats.total_levels }}</p>
            <table class="table">
                <thead>
                    <tr>
                        <th>Уровень</th>
                        <th>Количество танков</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="row in levelStats.level_distribution" :key="row.level_number">
                        <td>{{ row.level_number }}</td>
                        <td>{{ row.tanks_count }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>
