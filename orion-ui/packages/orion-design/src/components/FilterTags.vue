<template>
  <div :ref="refs.container" class="filter-tags">
    <div class="filter-tags__tags">
      <template v-for="(filter, index) in filters" :key="index">
        <FilterTag :ref="refs.tags" class="filter-tags__tag" v-bind="{ filter, dismissible, autoHide }" @dismiss="emit('dismiss', filter)" />
      </template>
    </div>
    <template v-if="hiddenCount">
      <DismissibleTag class="filter-tags__hidden" :style="styles" :label="moreLabel" />
      <DismissibleTag class="filter-tags__hidden-placeholder" :label="moreLabel" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue'
  import DismissibleTag from './DismissibleTag.vue'
  import FilterTag from '@/components/FilterTag.vue'
  import { FilterState } from '@/stores/filters'

  const emit = defineEmits<{
    (event: 'dismiss', filter: FilterState): void,
  }>()

  type Props = {
    filters: FilterState[],
    dismissible?: boolean,
    autoHide?: boolean,
  }

  const props = defineProps<Props>()

  const refs = {
    container: ref<HTMLDivElement>(),
    tags: ref<InstanceType<typeof FilterTag>[]>([]),
  }

  const hiddenCount = computed(() => refs.tags.value.filter(tag => tag.hidden).length)
  const moreLabel = computed(() => `${hiddenCount.value} more`)
  const styles = computed(() => {
    if (refs.container.value === undefined) {
      return null
    }

    const tagsComponents = refs.tags.value
    const sorted = tagsComponents.sort((a, b) => props.filters.indexOf(a.filter as FilterState) - props.filters.indexOf(b.filter as FilterState))
    const firstHidden = sorted.find(tag => tag.hidden)

    if (firstHidden?.el === undefined) {
      return null
    }

    const containerRect = refs.container.value.getBoundingClientRect()
    const tagRect = firstHidden.el.getBoundingClientRect()
    const left = tagRect.left - containerRect.left

    return {
      left: `${left}px`,
    }
  })
</script>

<style lang="scss">
.filter-tags {
  position: relative;
  display: flex;
  gap: var(--m-1);
}

.filter-tags__tags {
  display: flex;
  gap: var(--m-1);
  min-width: 0;
}

.filter-tags__tag {
  opacity: 1;
}

.filter-tags__hidden {
  flex-grow: 1;
}

.filter-tags__hidden {
  position: absolute;
}

.filter-tags__hidden-placeholder {
  visibility: hidden;
}
</style>