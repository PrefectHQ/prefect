<template>
  <Card class="menu font--primary" height="100%" tabindex="0">
    <template v-if="!media.md" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <h3
          class="d-flex align-center font--primary font-weight-semibold ml-auto"
        >
          <i class="pi pi-star-fill text--grey-80 mr-1" />
          Save Search
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          class="ml-auto"
          flat
          @click="close"
        />
      </div>
    </template>
    <template v-else v-slot:header>
      <h3 class="pa-2 font--primary font-weight-semibold">Save Search</h3>
    </template>

    <div class="menu-content pa-2">
      <Input label="Name" placeholder="New Filter" v-model="name" />

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
          v-if="!!media.md"
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
          :width="!media.md ? '100%' : 'auto'"
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
import { computed, ref, getCurrentInstance } from 'vue'
import { useStore } from 'vuex'
import { parseFilters, FilterObject } from './util'
import { Api, Endpoints } from '@/plugins/api'
import Tag from './Tag.vue'
import media from '@/utilities/media'

const store = useStore()
const instance = getCurrentInstance()
const emit = defineEmits(['close'])
const loading = ref(false)

const name = ref('')

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
