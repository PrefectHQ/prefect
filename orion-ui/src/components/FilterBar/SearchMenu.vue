<template>
  <Card class="menu font--primary" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <h3 class="d-flex align-center font--secondary ml-auto">
          <i class="pi pi-search-line mr-1" />
          Search
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          flat
          class="ml-auto"
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>

    <div class="menu-content">
      <transition name="fade" mode="out-in">
        <div
          v-if="loading"
          class="
            my-6
            d-flex
            flex-column
            align-center
            justify-center
            font--secondary
          "
        >
          <Loader :loading="loading" />
        </div>
        <div
          v-else-if="error"
          class="
            my-6
            d-flex
            flex-column
            align-center
            justify-center
            font--secondary
          "
        >
          <i class="pi pi-error-warning-line pi-3x" />
          <h2>Couldn't fetch saved searches</h2>
        </div>
        <div v-else class="justify-self-start">
          <div
            v-for="search in searches"
            :key="search.id"
            class="
              pa-2
              font--primary
              body
              search-item
              d-flex
              justify-space-between
            "
            @click.self="applyFilter"
          >
            <div>{{ search.name }}</div>

            <IconButton
              flat
              icon="pi-delete-bin-line text--grey-20 pi-sm"
              @click="remove(search.id)"
            />
          </div>
        </div>
      </transition>
    </div>

    <template v-if="smAndDown" v-slot:actions>
      <CardActions class="pa-2 menu-actions d-flex align-center justify-end">
        <Button
          color="primary"
          height="35px"
          :width="smAndDown ? '100%' : 'auto'"
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
import { Api, Endpoints } from '@/plugins/api'

const instance = getCurrentInstance()
const emit = defineEmits(['close'])

const searches = ref<{ name: string; id: string; filters: any }[]>([])
const loadingIds = ref<string[]>([])
const error = ref(false)
const loading = ref(false)

const getSavedSearches = async () => {
  loading.value = true
  const query = Api.query({
    endpoint: Endpoints.saved_searches,
    options: { paused: true }
  })

  const res = await query.fetch()

  if (res.response.error) error.value = res.response.error
  else searches.value = res.response.value
  loading.value = false
}

const close = () => {
  emit('close')
}

const applyFilter = () => {
  // emit('close')
}

const remove = async (id: string) => {
  loadingIds.value.push(id)

  const query = await Api.query({
    endpoint: Endpoints.delete_search,
    body: {
      id: id
    },
    options: { paused: true }
  })

  const res = await query.fetch()

  instance?.appContext.config.globalProperties.$toast.add({
    type: res.error ? 'error' : 'success',
    content: res.error ? `Error: ${res.error}` : 'Search removed',
    timeout: 10000
  })

  loadingIds.value.splice(loadingIds.value.indexOf(id), 1)
}

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
})

getSavedSearches()
</script>

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;

.menu {
  border-radius: 0;
  position: relative;

  .menu-content {
    border-top: 1px solid $secondary-hover;
    border-radius: 0 !important;
    overscroll-behavior: contain;
    height: 100%;
    overflow: auto;

    @media (max-width: 640px) {
      width: 100%;
    }
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

.search-item {
  cursor: pointer;

  &:hover,
  &:focus {
    background-color: $blue-5;
    color: $primary;

    ::v-deep(i) {
      color: $grey-40 !important;
    }
  }

  ::v-deep(i) {
    &:hover,
    &:focus {
      color: $error !important;
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
