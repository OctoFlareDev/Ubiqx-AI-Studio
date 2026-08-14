<script setup lang="ts">
import { Box, FolderKanban, Images, UserRound } from 'lucide-vue-next'
import { computed } from 'vue'

import { useStudioStore } from '@/stores/studio'

const studio = useStudioStore()
const displayName = computed(() => studio.profile?.display_name ?? 'Local Designer')

function showProjects() {
  studio.closeProject()
}

function openAssets() {
  studio.setActivePanel('assets')
}
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <span class="brand-mark"><Box :size="18" /></span>
      <span class="brand-name">Ubiqx</span>
    </div>

    <nav class="primary-nav" aria-label="Primary navigation">
      <button
        class="nav-item"
        :class="{ active: !studio.currentProjectId }"
        type="button"
        aria-label="Projects"
        @click="showProjects"
      >
        <FolderKanban :size="18" />
        <span>Projects</span>
      </button>
      <button
        class="nav-item"
        :class="{ active: Boolean(studio.currentProjectId) && studio.activePanel === 'assets' }"
        type="button"
        aria-label="Assets"
        :disabled="!studio.currentProjectId"
        :title="studio.currentProjectId ? 'Open the project asset library' : 'Open a project to view assets'"
        @click="openAssets"
      >
        <Images :size="18" />
        <span>Assets</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <div class="profile">
        <span class="avatar"><UserRound :size="17" /></span>
        <span class="profile-name">{{ displayName }}</span>
      </div>
    </div>
  </aside>
</template>
