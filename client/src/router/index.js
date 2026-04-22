import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user_store'

import GarageView from '@/views/GarageView.vue'
import TanksView from '@/views/TanksView.vue'
import BattlesView from '@/views/BattlesView.vue'
import BattleHistoryView from '@/views/BattleHistoryView.vue'
import LevelsView from '@/views/LevelsView.vue'
import NationsView from '@/views/NationsView.vue'
import StatsView from '@/views/StatsView.vue'
import CrewmanView from '@/views/CrewmanView.vue'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        { path: '/', component: GarageView, meta: { requiresAuth: true } },
        { path: '/tanks', component: TanksView, meta: { requiresAuth: true } },
        { path: '/battles', component: BattlesView, meta: { requiresAuth: true } },
        { path: '/battle-history', component: BattleHistoryView, meta: { requiresAuth: true } },
        { path: '/levels', component: LevelsView, meta: { requiresAuth: true, requiresStaff: true, requires2FAForEdit: true } },
        { path: '/nations', component: NationsView, meta: { requiresAuth: true, requiresStaff: true, requires2FAForEdit: true } },
        { path: '/stats', component: StatsView, meta: { requiresAuth: true, requiresStaff: true } },
        { path: '/crewmen', component: CrewmanView, meta: { requiresAuth: true, requiresStaff: true, requires2FA: true } }
    ]
})

router.beforeEach(async (to, from, next) => {
    const userStore = useUserStore()
    if (userStore.userInfo.username === null && userStore.userInfo.is_authenticated === false) {
        await userStore.checkLogin()
    }
    
    if (to.meta.requiresAuth && !userStore.userInfo.is_authenticated) {
        next('/')
        return
    }
    
    if (to.meta.requiresStaff && !userStore.userInfo.is_staff) {
        next('/')
        return
    }
    
    if (to.meta.requires2FA === true && !userStore.userInfo.second) {
        next('/')
        return
    }
    
    next()
})

export default router