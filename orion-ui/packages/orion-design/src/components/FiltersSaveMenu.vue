<template>
  <m-card class="filters-save-menu">
    <template #header>
      <div class="filters-save-menu__header">
        <p class="filters-save-menu__title">
          <i class="filters-save-menu__icon pi pi-star-fill" />
          Save Search
        </p>
        <m-icon-button
          icon="pi-close-line"
          class="filters-save-menu__close"
          width="34px"
          height="34px"
          flat
          @click="emit('close')"
        />
      </div>
    </template>

    <div class="filters-save-menu__content">
      <m-input v-model="name" label="Name" placeholder="New Filter" class="mb-2" />
      <FilterTags :filters="filtersStore.all" class="filters-save-menu__tags" />
    </div>

    <template #actions>
      <div class="filters-save-menu__actions">
        <m-button flat @click="emit('close')">
          Cancel
        </m-button>
        <m-button color="primary" :disabled="disabled" @click="save">
          Save
        </m-button>
      </div>
    </template>
  </m-card>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/miter-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import FilterTags from '@/components/FilterTags.vue'
  import { searchApiKey } from '@/services/SearchApi'
  import { useFiltersStore } from '@/stores/filters'
  import { Filter } from '@/types/filters'
  import { inject } from '@/utilities/inject'
  import { omit } from '@/utilities/object'

  const emit = defineEmits<{
    (event: 'close'): void,
  }>()

  const filtersStore = useFiltersStore()
  const name = ref('')
  const loading = ref(false)
  const disabled = computed(() => loading.value || name.value.length === 0)

  const searchApi = inject(searchApiKey)
  const searchesSubscription = useSubscription(searchApi.getSearches)

  function save(): void {
    loading.value = true

    const payload = filtersStore.all.map(filter => omit(filter, ['id'])) as Filter[]

    searchApi.createSearch(name.value, payload)
      .then(() => {
        showToast('Saved search', 'success')

        searchesSubscription.refresh()

        emit('close')
      })
      .catch(error => {
        console.error(error)
        showToast('Failed to save search', 'error')
      })
      .finally(() => {
        loading.value = true
      })

  }
</script>

<style lang="scss">
@use 'sass:map';

.filters-save-menu__header {
  padding: var(--p-2);
  display: flex;
}

.filters-save-menu__title {
  margin: 0;
  font-weight: 600;
  font-size: 18px;
  letter-spacing: .24px;
  line-height: 22px;
  display: flex;
  align-items: center;
  margin-left: auto;

  @media (min-width: map.get($breakpoints, 'md')) {
    margin-left: 0;
  }
}

.filters-save-menu__icon {
  margin-right: var(--m-1);
  color: var(--grey-80);

  @media (min-width: map.get($breakpoints, 'md')) {
    display: none;
  }
}

.filters-save-menu__close {
  margin-left: auto;

  @media (min-width: map.get($breakpoints, 'md')) {
    display: none;
  }
}

.filters-save-menu__content {
  border-top: solid 1px var(--secondary-hover);
  padding: var(--p-2);
}

.filters-save-menu__tags {
  display: flex;
  flex-wrap: wrap;
}

.filters-save-menu__actions {
  border-top: solid 1px var(--secondary-hover);
  padding: var(--p-2);
  display: flex;
  gap: var(--m-1);
  justify-content: space-between;
}

.filters-save-menu .filter-tags__tags {
  flex-wrap: wrap;
}
</style>