<script setup lang="ts">
import { computed, onMounted } from 'vue'

import AppSidebar from '@/components/AppSidebar.vue'
import ProjectListView from '@/views/ProjectListView.vue'
import StudioWorkspace from '@/views/StudioWorkspace.vue'
import { useStudioStore } from '@/stores/studio'

const studio = useStudioStore()
const showWorkspace = computed(() => Boolean(studio.currentProjectId))

onMounted(() => {
  void studio.boot()
})
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="app-main">
      <StudioWorkspace v-if="showWorkspace" />
      <ProjectListView v-else />
    </main>
  </div>
</template>

