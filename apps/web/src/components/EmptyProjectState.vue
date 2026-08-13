<script setup lang="ts">
import { FolderPlus } from 'lucide-vue-next'

const emit = defineEmits<{
  create: []
}>()
</script>

<template>
  <section class="empty-state">
    <span class="empty-icon"><FolderPlus :size="30" /></span>
    <h2>Create your first project</h2>
    <p>Start with an empty scene or import a PSD design.</p>
    <button class="primary-button" type="button" @click="emit('create')">
      <FolderPlus :size="17" />
      New project
    </button>
  </section>
</template>

