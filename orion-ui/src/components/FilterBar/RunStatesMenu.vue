<template>
  <Card class="run-states-menu" miter shadow="sm" tabindex="0">
    <div class="menu-content pa-2">
      <div class="font-weight-semibold">Select Run States</div>
      <hr class="hr" />

      <a
        class="font--secondary text--primary text-decoration-none my-2 d-block"
        @click="toggleAll"
      >
        Select All
      </a>

      <Checkbox
        v-for="state in states"
        :key="state.type"
        v-model="state.checked"
        class="d-flex my-1 font--secondary checkbox text-left"
      >
        <span>{{ state.name }}</span>
      </Checkbox>
    </div>

    <template v-slot:actions>
      <hr class="hr" />

      <div class="pa-2">
        <Button class="mr-1" outlined @click="emit('close')">Cancel</Button>
        <Button color="primary" @click="apply">Apply</Button>
      </div>
    </template>
  </Card>
</template>

<script lang="ts" setup>
import { defineEmits, ref, onBeforeMount } from 'vue'
import { RunState } from '@/typings/global'
import { useStore } from 'vuex'

const store = useStore()
const emit = defineEmits(['close'])

const storeState = [...store.getters.globalFilter.states].map(
  (s: RunState) => s.type
)

const states = ref<{ name: string; type: string; checked: boolean }[]>([
  { name: 'Scheduled', type: 'SCHEDULED', checked: false },
  { name: 'Pending', type: 'PENDING', checked: false },
  { name: 'Running', type: 'RUNNING', checked: false },
  { name: 'Completed', type: 'COMPLETED', checked: false },
  { name: 'Failed', type: 'FAILED', checked: false },
  { name: 'Cancelled', type: 'CANCELLED', checked: false }
  //   { name: 'Awaiting Retry', value: 'AWAITING_RETRY' },
  //   { name: 'Retrieved Cache', value: 'CACHED' },
  //   { name: 'Crashed', value: 'CRASHED' },
])

const toggleAll = () => {
  const checked = states.value.every((s) => s.checked)
  states.value.forEach((s) => (s.checked = !checked))
}

const apply = () => {
  store.commit(
    'states',
    states.value
      .filter((s) => s.checked)
      .map((s) => {
        return { name: s.name, type: s.type }
      })
  )
  emit('close')
}

onBeforeMount(() => {
  states.value.forEach((s) => {
    s.checked = storeState.includes(s.type)
  })
})
</script>

<style lang="scss" scoped>
.run-states-menu {
  height: auto;
}

hr {
  border: 0;
  border-bottom: 1px solid;
  color: $grey-10 !important;
  width: 100%;
}

.checkbox {
  align-items: center;
  display: flex;
  margin-left: 0 !important;
  width: min-content;

  ::v-deep(input) {
    -moz-appearance: inherit;
  }
}
</style>
