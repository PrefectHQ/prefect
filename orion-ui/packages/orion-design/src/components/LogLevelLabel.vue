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

<style lang="css">
:root {
  --log-level-not-set: #8EA0AE;
  --log-level-info: #8EA0AE;
  --log-level-debug: #024DFD;
  --log-level-warning: #8EA0AE;
  --log-level-error: #FB4E4E;
  --log-level-critical: #B82E2E;
}

.log-level-label {
  display: inline-block;
  font-family: barlow;
  font-size: 13px;
  font-weight: 600;
  height: 20px;
  border-radius: 4px;
  padding: 0 8px;
  line-height: 18px;
  color: #fff;
  text-align: center;
}

.log-level-label--not-set,
.log-level-label--info {
  background-color: var(--log-level-info);
}

.log-level-label--debug {
  background-color: var(--log-level-debug);
}

.log-level-label--warning {
  background-color: var(--log-level-warning);
}

.log-level-label--error {
  background-color: var(--log-level-error);
}

.log-level-label--critical {
  background-color: var(--log-level-critical);
}
</style>
