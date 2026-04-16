<script setup>
import { ref, onBeforeMount } from 'vue';
import axios from 'axios';
import { useUserStore } from '@/stores/user_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';

const userStore = useUserStore();
const { userInfo } = storeToRefs(userStore);

const tankStats = ref(null);
const battleStats = ref(null);
const nationStats = ref(null);
const levelStats = ref(null);
const loading = ref(true);

async function loadAllStats() {
    loading.value = true;
    try {
        const [ts, bs, ns, ls] = await Promise.all([
            axios.get('/api/tanks/stats/'),
            axios.get('/api/battles/stats/'),
            axios.get('/api/nations/stats/'),
            axios.get('/api/levels/stats/')
        ]);
        tankStats.value = ts.data;
        battleStats.value = bs.data;
        nationStats.value = ns.data;
        levelStats.value = ls.data;
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
        showError('Ошибка', 'Не удалось загрузить статистику');
    } finally {
        loading.value = false;
    }
}

async function exportAllToExcel() {
    try {
        const response = await axios.get('/api/user/export-all-stats/', { responseType: 'blob' });
        const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const link = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.setAttribute('download', 'full_statistics.xlsx');
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(objectUrl);
        showSuccess('Экспорт завершён', 'Файл statistics.xlsx скачан');
    } catch (error) {
        console.error('Ошибка экспорта:', error);
        showError('Ошибка', 'Не удалось скачать файл');
    }
}

onBeforeMount(() => {
    loadAllStats();
});
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated && userInfo.is_staff">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h2 class="stats-title">Статистика</h2>
                <button class="btn-custom-success" @click="exportAllToExcel">
                    📊 Экспорт всей статистики в Excel
                </button>
            </div>

            <div v-if="loading" class="text-center p-5">
                <div class="alert-custom-info">Загрузка статистики...</div>
            </div>

            <div v-else>
                <!-- Статистика танков -->
                <div class="custom-card mb-4" v-if="tankStats">
                    <div class="custom-card-header bg-primary">Статистика танков</div>
                    <div class="custom-card-body">
                        <div class="row text-center">
                            <div class="col-md-3">
                                <h3 class="text-primary">{{ tankStats.total_tanks || 0 }}</h3>
                                <p>Всего танков</p>
                            </div>
                            <div class="col-md-3">
                                <h3 class="text-success">{{ tankStats.avg_level?.toFixed(1) || 0 }}</h3>
                                <p>Средний уровень</p>
                            </div>
                            <div class="col-md-3">
                                <h3 class="text-warning">{{ tankStats.max_level || 0 }}</h3>
                                <p>Макс. уровень</p>
                            </div>
                            <div class="col-md-3">
                                <h3 class="text-info">{{ tankStats.min_level || 0 }}</h3>
                                <p>Мин. уровень</p>
                            </div>
                        </div>
                        <div class="alert alert-info mt-3">
                            <strong>Самая популярная нация:</strong> {{ tankStats.most_popular_nation || '—' }}
                        </div>
                    </div>
                </div>

                <!-- Статистика боёв -->
                <div class="custom-card mb-4" v-if="battleStats">
                    <div class="custom-card-header bg-success">Статистика боёв</div>
                    <div class="custom-card-body">
                        <div class="row text-center">
                            <div class="col-md-3">
                                <h3 class="text-primary">{{ battleStats.total_battles || 0 }}</h3>
                                <p>Всего боёв</p>
                            </div>
                            <div class="col-md-3">
                                <h3 class="text-success">{{ battleStats.victories || 0 }}</h3>
                                <p>Побед</p>
                            </div>
                            <div class="col-md-3">
                                <h3 class="text-danger">{{ battleStats.defeats || 0 }}</h3>
                                <p>Поражений</p>
                            </div>
                            <div class="col-md-3">
                                <h3 class="text-warning">{{ battleStats.win_rate || 0 }}%</h3>
                                <p>Winrate</p>
                            </div>
                        </div>
                        <div class="alert alert-info mt-3">
                            <strong>Всего заработано:</strong> {{ battleStats.total_reward || 0 }} 💰
                        </div>
                    </div>
                </div>

                <!-- Статистика наций -->
                <div class="custom-card mb-4" v-if="nationStats">
                    <div class="custom-card-header bg-warning text-dark">Статистика наций</div>
                    <div class="custom-card-body">
                        <div class="row text-center">
                            <div class="col-md-4">
                                <h3>{{ nationStats.total_nations || 0 }}</h3>
                                <p>Всего наций</p>
                            </div>
                            <div class="col-md-4">
                                <h3>{{ nationStats.total_tanks || 0 }}</h3>
                                <p>Всего танков</p>
                            </div>
                            <div class="col-md-4">
                                <h3>{{ nationStats.avg_tanks_per_nation?.toFixed(1) || 0 }}</h3>
                                <p>Среднее танков на нацию</p>
                            </div>
                        </div>
                        <div class="alert alert-info mt-3">
                            <strong>Самая популярная нация:</strong> {{ nationStats.most_popular_nation || '—' }} 
                            ({{ nationStats.most_popular_tanks_count || 0 }} танков)
                        </div>
                    </div>
                </div>

                <!-- Статистика уровней -->
                <div class="custom-card mb-4" v-if="levelStats">
                    <div class="custom-card-header bg-info text-white">Статистика уровней</div>
                    <div class="custom-card-body">
                        <div class="row text-center">
                            <div class="col-md-3">
                                <h3>{{ levelStats.total_levels || 0 }}</h3>
                                <p>Всего уровней</p>
                            </div>
                            <div class="col-md-3">
                                <h3>{{ levelStats.min_level || 0 }}</h3>
                                <p>Мин. уровень</p>
                            </div>
                            <div class="col-md-3">
                                <h3>{{ levelStats.max_level || 0 }}</h3>
                                <p>Макс. уровень</p>
                            </div>
                            <div class="col-md-3">
                                <h3>{{ levelStats.avg_level?.toFixed(1) || 0 }}</h3>
                                <p>Средний уровень</p>
                            </div>
                        </div>
                        <div class="mt-3">
                            <strong>Распределение танков по уровням:</strong>
                            <div class="mt-2" v-for="dist in levelStats.level_distribution" :key="dist.level_number">
                                <div class="d-flex justify-content-between">
                                    <span>Уровень {{ dist.level_number }}:</span>
                                    <span>{{ dist.tanks_count || 0 }} танков</span>
                                </div>
                                <div class="progress mb-2">
                                    <div class="progress-bar bg-danger" 
                                         :style="{ width: (dist.tanks_count / tankStats.total_tanks * 100) + '%' }">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else-if="userInfo && userInfo.is_authenticated && userInfo.is_staff && !userInfo.second" class="alert-custom-warning">
            Статистика доступна администраторам
        </div>
        <div v-else class="alert-custom-warning">Доступ только для администраторов</div>
    </div>
</template>

<style scoped>
.stats-title {
    color: #ffffff !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
}

.progress {
    height: 20px;
    background-color: #e9ecef;
    border-radius: 10px;
    overflow: hidden;
}
.progress-bar {
    transition: width 0.3s ease;
}
</style>