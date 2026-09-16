import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home,
    },
    {
      path: '/notes',
      name: 'notes',
      component: () => import('../views/NoteList.vue'),
    },
    {
      path: '/notes/:id',
      name: 'note-preview',
      component: () => import('../views/NotePreview.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/ChatGlobal.vue'),
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
