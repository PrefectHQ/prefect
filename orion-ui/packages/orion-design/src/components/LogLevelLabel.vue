<template>
  <span class="log-level-label correct-text" :class="classes">
    {{ label }}
  </span>
</template>

<script lang="ts" setup>
  import { snakeCase } from '@/utilities/strings'
  import { computed } from 'vue'
  import { LogLevel } from '../services/LogLevel'

  const props = defineProps({
    level: {
      type: Number,
      required: true,
    },
  })

  const label = computed(() => LogLevel.GetLabel(props.level))

  const classes = computed(() => {
    return `log-level-label--${snakeCase(label.value)}`
  })
</script>

<style lang="scss" scoped>
.log-level-label {
  display: inline-block;
  font-family: barlow;
  font-size: 13px;
  font-weight: 600;
  height: 20px;
  border-radius: 4px;
  padding: 0 8px;
  line-height: 18px;
}

.log-level-label--not-set,
.log-level-label--info {
  background-color: #8EA0AE;
}

.log-level-label--debug {
  background-color: #024DFD;
}

.log-level-label--warning {
  background-color: #8EA0AE;
}

.log-level-label--error {
  background-color: #F6A609;
}

.log-level-label--critical {
  background-color: #B82E2E;
}
</style>
