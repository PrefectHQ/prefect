<template>
  <template v-if="crumb.loading">
    <div class="bread-crumb--loading">
      <span v-skeleton="true">
        Loading...
      </span>
    </div>
  </template>
  <template v-else>
    <component
      :is="component"
      class="bread-crumb"
      :class="classes.crumb"
      :to="crumb.to"
    >
      {{ crumb.text }}
    </component>
  </template>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { Crumb } from '@/models/Crumb'

  const props = defineProps<{ crumb: Crumb }>()

  const showClickable = computed(() => typeof props.crumb.clickable === 'boolean' ? props.crumb.clickable : !!props.crumb.to)
  const component = computed(() => showClickable.value && props.crumb.to ? 'router-link' : 'div')
  const classes = computed(() => ({
    crumb: {
      'bread-crumb--clickable': showClickable.value,
    },
  }))
</script>

<style lang="scss">
.bread-crumb--loading {
  overflow: hidden;
}

.bread-crumb--clickable {
  color: var(--primary);
}

.bread-crumb--clickable:hover,
.bread-crumb--clickable:active {
  cursor: pointer;
}
</style>
