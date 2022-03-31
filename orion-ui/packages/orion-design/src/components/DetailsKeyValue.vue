<template>
  <div class="details-key-value" :class="{ 'details-key-value--stacked': stacked, 'details-key-value--not-stacked': !stacked }">
    <div class="details-key-value__label">
      {{ label }}
    </div>
    <div class="details-key-value__value">
      <slot v-bind="{ emptyValue }">
        {{ value ?? emptyValue }}
      </slot>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { PropType } from 'vue'

  defineProps({
    label: {
      type: String,
      required: true,
    },
    value: {
      type: String as PropType<string | null | undefined>,
      required: false,
      default: null,
    },
    stacked: {
      type: Boolean,
      required: false,
    },
  })

  const emptyValue = '--'
</script>

<style lang="scss">
.details-key-value {
  display: flex;
  gap: 2px;
  font-size: 13px;
  letter-spacing: -.09px;
  line-height: 18px;
  font-weight: 600;
}

.details-key-value__label {
  color: var(--grey-40);
}

.details-key-value__value {
  color: var(--grey-80);
  overflow: hidden;
  text-overflow: ellipsis;
}

.details-key-value--not-stacked {
  white-space: nowrap;
}

.details-key-value--stacked {
  flex-direction: column;
  font-weight: 400;
  width: 100%;

  .details-key-value__label {
    color: var(--grey-80);
    font-weight: 600;
  }

  .details-key-value__value {
    font-family: var(--font-secondary);

  }
}
</style>
