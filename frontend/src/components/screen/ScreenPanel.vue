<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
  span?: 1 | 2 | 3
}>()
</script>

<template>
  <article class="panel" :class="`span-${span || 1}`">
    <header class="panel-head">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div class="panel-body">
      <slot />
    </div>
  </article>
</template>

<style scoped>
.panel {
  background: rgba(12, 28, 40, 0.72);
  border: 1px solid rgba(94, 168, 170, 0.28);
  border-radius: 10px;
  padding: 12px 14px 10px;
  display: flex;
  flex-direction: column;
  min-height: 300px;
  backdrop-filter: blur(6px);
  grid-column: span 1;
}

.panel.span-2 {
  grid-column: span 2;
}

.panel.span-3 {
  grid-column: span 3;
  min-height: auto;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.panel-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #e7f4f1;
}

.panel-head p {
  margin: 3px 0 0;
  font-size: 11px;
  color: rgba(180, 210, 220, 0.72);
}

.panel-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1100px) {
  .panel,
  .panel.span-2,
  .panel.span-3 {
    grid-column: span 1;
  }
}
</style>
