<template>
  <component
    :is="component"
    class="bread-crumb"
    :class="classes.crumb"
    :to="to"
    @click="callback"
  >
    <span v-if="crumb.loading" v-skeleton="true" class="bread-crumb__loading">
      Loading...
    </span>
    <span v-else>
      {{ crumb.text }}
    </span>
  </component>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { Crumb, crumbIsCallback, crumbIsRouting } from '@/models/Crumb'

  const props = defineProps<{ crumb: Crumb }>()

  const to = computed(() => {
    return crumbIsRouting(props.crumb) ? props.crumb.action : undefined
  })

  const callback = computed(() => {
    return crumbIsCallback(props.crumb) ? props.crumb.action : undefined
  })

  const showClickable = computed(() => {
    return !!to.value || !!callback.value
  })

  const component = computed(() => {
    return !props.crumb.loading && showClickable.value && !!to.value ? 'router-link' : 'span'
  })

  const classes = computed(() => ({
    crumb: {
      'bread-crumb--clickable': showClickable.value,
    },
  }))
</script>

<style lang="scss">
.bread-crumb--clickable {
  color: var(--primary);
}

.bread-crumb--clickable:hover,
.bread-crumb--clickable:active {
  cursor: pointer;
}
</style>
