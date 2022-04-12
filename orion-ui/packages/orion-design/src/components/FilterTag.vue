<template>
  <div ref="el" class="filter-tag" :class="classes">
    <DismissibleTag v-bind="{ label, dismissible }" @dismiss="dismiss(filter)" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref, Ref, defineExpose, inject } from 'vue'
  import DismissibleTag from '@/components/DismissibleTag.vue'
  import { useIntersectionObserver } from '@/compositions/useIntersectionObserver'
  import { filtersDefaultObjectKey, FilterService } from '@/services/FilterService'
  import { Filter } from '@/types/filters'

  const emit = defineEmits<{
    (event: 'dismiss', filter: Required<Filter>): void,
  }>()
  type Props = {
    filter: Required<Filter>,
    dismissible?: boolean,
    autoHide?: boolean,
  }

  const props = defineProps<Props>()
  const defaultObject = inject(filtersDefaultObjectKey, 'flow_run')
  const label = computed<string>(() => FilterService.stringify(props.filter, { defaultObject }))
  const el: Ref<HTMLDivElement | undefined> = ref()
  const hidden = ref(false)
  const observed = ref(false)

  defineExpose({
    hidden,
    el,
    filter: props.filter,
  })

  const classes = computed(() => ({
    'filter-tag--auto-hide': props.autoHide,
    'filter-tag--visible': observed.value && !hidden.value && props.autoHide,
  }))

  onMounted(() => {
    const root = el.value?.parentElement

    const { observe } = useIntersectionObserver(intersect, {
      root,
      threshold: 1,
    })

    observe(el)
  })

  function intersect(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      hidden.value = !entry.isIntersecting
      observed.value = true
    })
  }

  function dismiss(filter: Required<Filter>): void {
    if (props.dismissible) {
      emit('dismiss', filter)
    }
  }
</script>

<style lang="scss">
.filter-tag--auto-hide {
  visibility: hidden;
}

.filter-tag--visible {
  visibility: visible;
}
</style>