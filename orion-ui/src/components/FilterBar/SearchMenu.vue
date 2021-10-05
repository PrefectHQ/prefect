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

    <div class="menu-content d-flex align-center justify-center pa-2">
      <div
        v-if="error"
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
      <div v-else>
        <div v-for="search in searches" :key="search.id">{{ search }}</div>
      </div>
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

const searches = ref([])
const error = ref(true)

const getSavedSearches = async () => {
  const query = Api.query({
    endpoint: Endpoints.saved_searches,
    options: { paused: true }
  })

  const res = await query.fetch()

  if (res.response.error) error.value = res.response.error
  else searches.value = res.response.value
}

const close = () => {
  emit('close')
}

const save = () => {
  console.log('save')
}

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
})

getSavedSearches()
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
</style>
