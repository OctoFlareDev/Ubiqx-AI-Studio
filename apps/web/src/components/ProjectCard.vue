<script setup lang="ts">
import {
  Archive,
  Check,
  FolderOpen,
  Pencil,
  Trash2,
  X,
} from 'lucide-vue-next'
import { ref } from 'vue'

import type { Project } from '@/types'

const props = defineProps<{
  project: Project
  archived?: boolean
}>()

const emit = defineEmits<{
  open: [projectId: string]
  rename: [projectId: string, name: string]
  archive: [projectId: string]
  restore: [projectId: string]
  delete: [projectId: string]
}>()

const editing = ref(false)
const draftName = ref(props.project.name)

function startEdit(event: MouseEvent) {
  event.stopPropagation()
  draftName.value = props.project.name
  editing.value = true
}

function commitEdit() {
  const name = draftName.value.trim()
  if (name) emit('rename', props.project.id, name)
  editing.value = false
}

function cancelEdit() {
  editing.value = false
}

function formattedDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>

<template>
  <article
    class="project-card"
    role="button"
    tabindex="0"
    :aria-label="`Open project ${project.name}`"
    @click="emit('open', project.id)"
    @keydown.enter="emit('open', project.id)"
    @keydown.space.prevent="emit('open', project.id)"
  >
    <div class="project-thumb" aria-hidden="true">
      <FolderOpen :size="30" />
    </div>
    <div class="project-card-body">
      <div v-if="editing" class="rename-row" @click.stop>
        <input v-model="draftName" type="text" aria-label="Project name" @keyup.enter="commitEdit" />
        <button class="icon-button" type="button" aria-label="Save name" @click="commitEdit">
          <Check :size="15" />
        </button>
        <button class="icon-button" type="button" aria-label="Cancel rename" @click="cancelEdit">
          <X :size="15" />
        </button>
      </div>
      <template v-else>
        <h3>{{ project.name }}</h3>
        <p>{{ formattedDate(project.updated_at) }}</p>
      </template>
    </div>
    <div v-if="!editing" class="project-actions" @click.stop>
      <button class="icon-button" type="button" aria-label="Rename project" title="Rename" @click="startEdit">
        <Pencil :size="15" />
      </button>
      <button v-if="!archived" class="icon-button" type="button" aria-label="Archive project" title="Archive" @click="emit('archive', project.id)">
        <Archive :size="15" />
      </button>
      <button v-else class="icon-button" type="button" aria-label="Restore project" title="Restore" @click="emit('restore', project.id)">
        <FolderOpen :size="15" />
      </button>
      <button class="icon-button danger" type="button" aria-label="Delete project" title="Delete" @click="emit('delete', project.id)">
        <Trash2 :size="15" />
      </button>
    </div>
  </article>
</template>
