<template>
  <Card class="timeframe-menu font--secondary" miter shadow="sm" tabindex="0">
    <div class="menu-content pa-2">
      <Radio
        v-model="timeframeSelector"
        :value="'standard'"
        :checked="timeframeSelector == 'standard'"
        class="mb-1 radio"
      >
        Standard
      </Radio>

      <Radio
        v-model="timeframeSelector"
        :value="'custom'"
        :checked="timeframeSelector == 'custom'"
        class="mb-1 radio"
        disabled
      >
        Custom
      </Radio>

      <div v-if="timeframeSelector == 'standard'">
        From:
        <select v-model="pastAmount">
          <option v-for="(option, i) in amountOptions" :value="option" :key="i">
            {{ option }}
          </option>
        </select>
        <select v-model="pastUnit">
          <option v-for="(option, i) in unitOptions" :value="option" :key="i">
            {{ option }}
          </option>
        </select>
        To:
        <select v-model="futureAmount">
          <option v-for="(option, i) in amountOptions" :value="option" :key="i">
            {{ option }}
          </option>
        </select>
        <select v-model="futureUnit">
          <option v-for="(option, i) in unitOptions" :value="option" :key="i">
            {{ option }}
          </option>
        </select>
      </div>
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
import { defineEmits, ref, defineProps } from 'vue'
import { useStore } from 'vuex'

const props = defineProps<{
  object: 'flow_runs' | 'task_runs'
}>()
const emit = defineEmits(['close'])
const store = useStore()

const from = store.getters.globalFilter[props.object].timeframe?.from || {
  value: 60,
  unit: 'minutes'
}
const to = store.getters.globalFilter[props.object].timeframe?.to || {
  value: 60,
  unit: 'minutes'
}
const pastAmount = ref(from.value)
const pastUnit = ref(from.unit)
const futureAmount = ref(to.value)
const futureUnit = ref(to.unit)

const timeframeSelector = ref('standard')

const amountOptions = [1, 5, 15, 24, 30, 60]

const unitOptions = ['minutes', 'hours', 'days']

const apply = () => {
  const from = {
    unit: pastUnit.value,
    value: pastAmount.value
  }

  const to = {
    unit: futureUnit.value,
    value: futureAmount.value
  }

  store.commit('timeframe', {
    object: props.object,
    dynamic: timeframeSelector.value == 'custom',
    from,
    to
  })
  emit('close')
}
</script>

<style lang="scss" scoped>
.timeframe-menu {
  height: auto;
  position: relative;
  width: 100%;

  .menu-content {
    .radio {
      > ::v-deep(input) {
        display: none;
      }
    }
  }
}

.timeframe-selector {
  height: 44px !important;
  width: 200px !important;
}

hr {
  border: 0;
  border-bottom: 1px solid;
  color: $grey-10 !important;
  width: 100%;
}
</style>
