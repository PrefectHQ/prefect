<template>
  <Card class="menu font--primary" height="100%" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <h3 class="d-flex align-center font--secondary ml-auto">
          <i class="pi pi-star-fill text--warning mr-1" />
          Save filter
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          class="ml-auto"
          flat
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>
    <template v-else v-slot:header>
      <div class="pa-2 d-flex justify-start align-center">
        <h4 class="d-flex align-center font--secondary">
          <i class="pi pi-star-fill mr-1 text--warning" />
          Save filter
        </h4>
      </div>
    </template>

    <div class="menu-content pa-2">
      <Input label="Name" v-model="name" />

      <div class="my-4">
        <Tag v-for="(filter, i) in filters" :key="i" class="mr--half mb--half">
          <i class="pi pi-xs mr--half" :class="filter.icon" />
          {{ filter.label }}
        </Tag>
      </div>
    </div>

    <template v-slot:actions>
      <CardActions class="pa-2 menu-actions d-flex align-center justify-end">
        <Button
          v-if="!smAndDown"
          flat
          height="35px"
          class="ml-auto mr-1"
          @click="close"
        >
          Cancel
        </Button>
        <Button
          color="primary"
          height="35px"
          :width="smAndDown ? '100%' : 'auto'"
          :disabled="!name || loading"
          @click="save"
        >
          Save
        </Button>
      </CardActions>
    </template>
  </Card>
</template>

<script lang="ts" setup>
import { computed, defineEmits, ref, getCurrentInstance } from 'vue'
import { useStore } from 'vuex'
import { parseFilters, FilterObject } from './util'
import { Api, Endpoints } from '@/plugins/api'
import Tag from './Tag.vue'

const store = useStore()
const instance = getCurrentInstance()
const emit = defineEmits(['close'])
const loading = ref(false)

const name = ref('New Filter')

const close = () => {
  emit('close')
}

const save = async () => {
  loading.value = true
  const gf = JSON.parse(JSON.stringify(store.getters.globalFilter))

  const query = await Api.query({
    endpoint: Endpoints.save_search,
    body: {
      name: name.value,
      filters: gf
    },
    options: { paused: true }
  })

  const res = await query.fetch()

  instance?.appContext.config.globalProperties.$toast.add({
    type: res.error ? 'error' : 'success',
    content: res.error ? `Error: ${res.error}` : 'Filter saved!',
    timeout: 10000
  })

  if (!res.error) {
    close()
  }
  loading.value = false
}

const filters = computed<FilterObject[]>(() => {
  return parseFilters(store.getters.globalFilter)
})

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
})
</script>

<style lang="scss" scoped>
.menu {
  border-radius: 0;
  position: relative;

  .menu-content {
    border-top: 1px solid $secondary-hover;
    border-radius: 0 !important;

    overscroll-behavior: contain;
    height: 100%;
    overflow: auto;

    @media (max-width: 1024px) {
      background-color: $grey-10;
    }

    @media (max-width: 640px) {
      background-color: $grey-10;
      width: 100%;
    }
  }

  hr {
    background-color: $grey-10;
    border: none;
    height: 2px;
  }

  .menu-actions {
    border-top: 1px solid $secondary-hover;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
    max-height: inherit;
  }

  .menu-container {
    position: relative;
  }
}
</style>
