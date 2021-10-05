<template>
  <div class="container">
    <div class="font-weight-semibold">Timeframe</div>

    <div class="my-2">
      <Radio
        v-model="timeframeSelector"
        :value="'standard'"
        :checked="timeframeSelector == 'standard'"
        class="radio"
      >
        Standard
      </Radio>

      <Radio
        v-model="timeframeSelector"
        :value="'custom'"
        :checked="timeframeSelector == 'custom'"
        class="radio"
      >
        Custom
      </Radio>
    </div>

    <div v-if="timeframeSelector == 'standard'">
      <div class="caption-small text-uppercase font-weight-semibold my-1">
        Past
      </div>
      <div class="d-flex">
        <NumberInput
          v-model="fromValue"
          step="1"
          class="d-inline-block selector"
        />

        <Select v-model="fromUnit" class="ml-2 d-inline-block selector">
          <Option v-for="u in unitOptions" :key="u" :value="u">{{ u }}</Option>
        </Select>
      </div>

      <div class="caption-small text-uppercase font-weight-semibold my-1">
        Upcoming
      </div>
      <div class="d-flex">
        <NumberInput
          v-model="toValue"
          step="1"
          class="d-inline-block selector"
        />

        <Select v-model="toUnit" class="ml-2 d-inline-block selector">
          <Option v-for="u in unitOptions" :key="u" :value="u">{{ u }}</Option>
        </Select>
      </div>
    </div>
    <div v-else> CUSTOM </div>
  </div>
</template>

<script lang="ts" setup>
import { timeframe } from '@/store/mutations'
import { defineEmits, ref, defineProps, watch, computed } from 'vue'

const props = defineProps<{
  modelValue: {
    dynamic: boolean
    from: { timestamp: Date; unit: string; value: number }
    to: { timestamp: Date; unit: string; value: number }
  }
}>()

const emit = defineEmits(['update:modelValue'])

const fromUnit = ref(props.modelValue.from.unit)
const toUnit = ref(props.modelValue.to.unit)
const fromValue = ref(props.modelValue.from.value)
const toValue = ref(props.modelValue.to.value)
const fromTimestamp = ref(props.modelValue.from.timestamp)
const toTimestamp = ref(props.modelValue.to.timestamp)

const value = computed(() => {
  return {
    dynamic: timeframeSelector.value == 'standard',
    from: {
      timestamp:
        timeframeSelector.value == 'standard' ? null : fromTimestamp.value,
      unit: fromUnit.value,
      value: fromValue.value
    },
    to: {
      timestamp:
        timeframeSelector.value == 'standard' ? null : toTimestamp.value,
      unit: toUnit.value,
      value: toValue.value
    }
  }
})

const timeframeSelector = ref('standard')

const unitOptions = ['minutes', 'hours', 'days']

watch([fromUnit, toUnit, fromValue, toValue], () => {
  emit('update:modelValue', value.value)
})
</script>

<style lang="scss" scoped>
.container {
  min-height: 400px !important;

  @media (max-width: 1024px) {
    min-height: 300px;
  }
}

.selector {
  height: 40px !important;
  width: auto !important;
  max-width: 200px !important;
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
