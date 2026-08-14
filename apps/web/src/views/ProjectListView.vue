<script setup lang="ts">
import { Archive, Plus, Search, X } from 'lucide-vue-next'
import { computed, ref } from 'vue'

import EmptyProjectState from '@/components/EmptyProjectState.vue'
import ProjectCard from '@/components/ProjectCard.vue'
import { useStudioStore } from '@/stores/studio'

const studio = useStudioStore()
const creating = ref(false)
const newProjectName = ref('')
const query = ref('')
const showArchived = ref(false)

const visibleProjects = computed(() => (showArchived.value ? studio.archivedProjects : studio.projects))
const filteredProjects = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return visibleProjects.value
  return visibleProjects.value.filter((project) => project.name.toLowerCase().includes(term))
})

function startCreate() {
  creating.value = true
  newProjectName.value = ''
}

async function createProject() {
  const name = newProjectName.value.trim() || 'Untitled Project'
  try {
    const project = await studio.createProject(name)
    await studio.openProject(project.id)
  } finally {
    creating.value = false
    newProjectName.value = ''
  }
}

async function openProject(projectId: string) {
  await studio.openProject(projectId)
}

async function renameProject(projectId: string, name: string) {
  await studio.renameProject(projectId, name)
}

async function archiveProject(projectId: string) {
  await studio.archiveProject(projectId)
}

async function deleteProject(projectId: string) {
  if (window.confirm('Delete this project?')) await studio.deleteProject(projectId)
}

async function restoreProject(projectId: string) {
  await studio.restoreProject(projectId)
}
</script>

<template>
  <div class="project-list-view">
    <header class="view-header">
      <div>
        <p class="eyebrow">Local workspace</p>
        <h1>Projects</h1>
      </div>
      <button class="primary-button" type="button" @click="startCreate">
        <Plus :size="17" />
        New project
      </button>
      <button class="secondary-button" type="button" @click="showArchived = !showArchived">
        {{ showArchived ? 'Active projects' : `Archived (${studio.archivedProjects.length})` }}
      </button>
    </header>

    <div class="project-toolbar">
      <label class="search-field">
        <Search :size="16" />
        <input v-model="query" type="search" placeholder="Search projects" aria-label="Search projects" />
        <button v-if="query" class="icon-button" type="button" aria-label="Clear search" @click="query = ''">
          <X :size="14" />
        </button>
      </label>
    </div>

    <div v-if="creating" class="create-row">
      <input
        v-model="newProjectName"
        type="text"
        aria-label="New project name"
        placeholder="Project name"
        @keyup.enter="createProject"
      />
      <button class="primary-button" type="button" @click="createProject">Create</button>
      <button class="secondary-button" type="button" @click="creating = false">Cancel</button>
    </div>

    <p v-if="studio.error" class="error-banner">{{ studio.error }}</p>

    <div v-if="studio.loading && studio.projects.length === 0" class="loading-grid">
      <div v-for="index in 4" :key="index" class="project-skeleton" />
    </div>

    <EmptyProjectState v-else-if="!showArchived && studio.projects.length === 0" @create="startCreate" />

    <section v-else-if="showArchived && studio.archivedProjects.length === 0" class="no-results-state" aria-live="polite">
      <Archive :size="24" />
      <h2>No archived projects</h2>
      <p>Archived projects will appear here so they can be restored.</p>
    </section>

    <section v-else-if="filteredProjects.length === 0" class="no-results-state" aria-live="polite">
      <Search :size="24" />
      <h2>No matching projects</h2>
      <p>Try a different search term or clear the filter.</p>
      <button class="secondary-button" type="button" @click="query = ''">
        <X :size="16" />
        Clear search
      </button>
    </section>

    <section v-else class="project-grid" aria-label="Project list">
      <ProjectCard
        v-for="project in filteredProjects"
        :key="project.id"
        :project="project"
        :archived="showArchived"
        @open="openProject"
        @rename="renameProject"
        @archive="archiveProject"
        @delete="deleteProject"
        @restore="restoreProject"
      />
    </section>
  </div>
</template>
