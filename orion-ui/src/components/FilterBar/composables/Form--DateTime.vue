<template>
  <div class="container">
    <div class="font-weight-semibold d-flex align-center">
      <i class="pi text--grey-40 mr-1 pi-sm" :class="icon" />
      {{ title }}
    </div>

    <form class="my-2 d-flex">
      <m-radio
        v-model="timeframeSelector"
        value="simple"
        :checked="timeframeSelector == 'simple'"
        class="mr-2"
      >
        Simple
      </m-radio>

      <m-radio
        v-model="timeframeSelector"
        value="custom"
        :checked="timeframeSelector == 'custom'"
      >
        Custom
      </m-radio>
    </form>

    <div v-if="timeframeSelector == 'simple'">
      <div class="caption-small text-uppercase font-weight-semibold my-1">
        Past
      </div>
      <div class="d-flex">
        <m-number-input
          v-model="fromValue"
          step="1"
          class="d-inline-block selector"
        />

        <m-simple-select
          v-model="fromUnit"
          :options="unitOptions"
          class="ml-2 d-inline-block selector"
        />
      </div>

      <div class="caption-small text-uppercase font-weight-semibold my-1">
        Upcoming
      </div>
      <div class="d-flex">
        <m-number-input
          v-model="toValue"
          step="1"
          class="d-inline-block selector"
        />

        <m-simple-select
          v-model="toUnit"
          :options="unitOptions"
          class="ml-2 d-inline-block selector"
        />
      </div>
    </div>
    <div v-else>
      <m-input
        :value="fromTimestamp?.toLocaleString()"
        type="date"
        label="Start Date"
        class="mb-2"
        @click="showFromDateTimeMenu = !showFromDateTimeMenu"
      />

      <teleport to=".application" v-if="showFromDateTimeMenu">
        <div class="date-picker pa-2">
          <h2 class="font-weight-semibold mb-2">Timeframe Start</h2>
          <m-date-picker v-model="tempFromTimestamp" />
          <m-time-picker v-model="tempFromTimestamp" class="py-1" />

          <hr />
          <div class="mt-2 d-flex align-center justify-end">
            <m-button
              flat
              height="36px"
              class="ml-auto mr-1"
              @click="showFromDateTimeMenu = false"
            >
              Cancel
            </m-button>
            <m-button
              color="primary"
              height="36px"
              @click="applyTempFromTimestamp"
            >
              Apply
            </m-button>
          </div>
        </div>
        <div class="overlay" @click="showFromDateTimeMenu = false" />
      </teleport>

      <m-input
        :value="toTimestamp?.toLocaleString()"
        type="date"
        label="End Date"
        @click="showToDateTimeMenu = !showToDateTimeMenu"
      />

      <teleport to=".application" v-if="showToDateTimeMenu">
        <div class="date-picker pa-2">
          <h2 class="font-weight-semibold">Timeframe End</h2>
          <m-date-picker v-model="tempToTimestamp" />
          <m-time-picker v-model="tempToTimestamp" class="py-1" />

          <hr />
          <div class="mt-2 d-flex align-center justify-end">
            <m-button
              flat
              height="36px"
              class="ml-auto mr-1"
              @click="showToDateTimeMenu = false"
            >
              Cancel
            </m-button>
            <m-button
              color="primary"
              height="36px"
              @click="applyTempToTimestamp"
            >
              Apply
            </m-button>
          </div>
        </div>
        <div class="overlay" @click="showToDateTimeMenu = false" />
      </teleport>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { RunTimeFrame } from '@/typings/global';
import { ref, watch, computed, withDefaults } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue?: RunTimeFrame
    title?: string
    icon?: string
  }>(),
  {
    modelValue: () => {
      return {
        dynamic: false,
        from: { timestamp: new Date(), unit: 'minutes', value: 60 },
        to: { timestamp: new Date(), unit: 'minutes', value: 60 }
      }
    },
    title: 'Timeframe',
    icon: 'pi-time-line'
  }
)

const emit = defineEmits(['update:modelValue'])

const showFromDateTimeMenu = ref(false)
const showToDateTimeMenu = ref(false)

const fromUnit = ref(props.modelValue.from.unit)
const toUnit = ref(props.modelValue.to.unit)
const fromValue = ref(props.modelValue.from.value)
const toValue = ref(props.modelValue.to.value)
const fromTimestamp = ref(props.modelValue.from.timestamp || new Date())
const toTimestamp = ref(props.modelValue.to.timestamp || new Date())

const tempFromTimestamp = ref(props.modelValue.from.timestamp || new Date())
const tempToTimestamp = ref(props.modelValue.to.timestamp || new Date())

const value = computed(() => {
  return {
    dynamic: timeframeSelector.value == 'simple',
    from: {
      timestamp:
        timeframeSelector.value == 'simple' ? null : fromTimestamp.value,
      unit: fromUnit.value,
      value: fromValue.value
    },
    to: {
      timestamp: timeframeSelector.value == 'simple' ? null : toTimestamp.value,
      unit: toUnit.value,
      value: toValue.value
    }
  }
})

const applyTempFromTimestamp = () => {
  fromTimestamp.value = new Date(tempFromTimestamp.value)
  showFromDateTimeMenu.value = false
}

const applyTempToTimestamp = () => {
  toTimestamp.value = new Date(tempToTimestamp.value)
  showToDateTimeMenu.value = false
}

const timeframeSelector = ref('simple')

const unitOptions = ['minutes', 'hours', 'days']

watch(
  [fromUnit, toUnit, fromValue, toValue, fromTimestamp, toTimestamp],
  () => {
    emit('update:modelValue', value.value)
  }
)
</script>

<style lang="scss" scoped>
.container {
  width: 100%;
}

> ::v-deep(.radio) {
  margin-left: 0 !important;
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

.position-relative {
  position: relative;
}

.date-picker {
  background-color: $white;
  box-shadow: $box-shadow-sm;
  border-radius: 4px;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  // max-width: 280px;
  // height: 100%;
  // max-height: 500px;
  width: auto;
  z-index: 11;

  .calendar {
    border: none !important;
  }

  .time-picker {
    padding: 4px 0 !important;
  }
}

.overlay {
  background-color: rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(1px);
  height: 100vh;
  width: 100vw;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
}

hr {
  background-color: $grey-10;
  border: none;
  height: 2px;
}
</style>
