<template>
  <m-input
    :value="formatted"
    :label="label"
    v-bind="{ type, ...$attrs }"
    @click="open"
    @keypress.space="open"
  />

  <teleport v-if="showPicker" to="[data-teleport-target='app']">
    <div class="date-time-input__picker">
      <m-date-picker v-model="tempValue" class="date-time-input__date" />
      <m-time-picker v-model="tempValue" class="date-time-input__time" />

      <hr>
      <div class="mt-2 d-flex align-center justify-end">
        <m-button
          flat
          height="36px"
          class="ml-auto mr-1"
          @click="showPicker = false"
        >
          Cancel
        </m-button>
        <m-button
          color="primary"
          height="36px"
          @click="applyTempValue"
        >
          Apply
        </m-button>
      </div>
    </div>
    <div class="date-time-input__overlay" @click="showPicker = false" />
  </teleport>
</template>

<script lang="ts">
  export default {
    inheritAttrs: false,
  }
</script>

<script lang="ts" setup>
  import { useMedia } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { formatDateTimeNumericInTimeZone, formatInTimeZone } from '@/utilities/dates'

  const props = defineProps<{
    label: string,
    value: Date | null,
  }>()

  const emit = defineEmits<{
    (event: 'update:value', value: Date): void,
  }>()

  const showPicker = ref(false)
  const tempValue = ref(props.value ?? new Date())
  const formatted = computed(() => {
    if (props.value == null) {
      return ''
    }

    if (isTouchMedia.value) {
      return formatInTimeZone(props.value, "yyyy-MM-dd'T'hh:mm")
    }

    return formatDateTimeNumericInTimeZone(props.value)
  })

  const isTouchMedia = useMedia('(pointer: coarse), (hover: none)')

  const type = computed(() => isTouchMedia.value ? 'datetime-local' : 'text')

  function open(): void {
    if (isTouchMedia.value) {
      return
    }

    showPicker.value = !showPicker.value
  }

  function applyTempValue(): void {
    emit('update:value', tempValue.value)
    showPicker.value = false
  }
</script>

<style lang="scss">
.date-time-input__picker {
  background-color: $white;
  box-shadow: $box-shadow-sm;
  border-radius: 4px;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: auto;
  z-index: var(--layer-datepicker);
  padding: var(--p-2);
}

.date-time-input__date {
  border: none !important;
}

.date-time-input__time {
  padding: 4px 0 !important;
  padding: var(--p-1) 0;
}

.date-time-input__overlay {
  background-color: rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(1px);
  height: 100vh;
  width: 100vw;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
}
</style>