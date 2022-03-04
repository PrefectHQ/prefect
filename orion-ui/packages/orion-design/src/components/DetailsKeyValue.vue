<template>
  <div class="details-key-value" :class="{ 'details-key-value--stacked': stacked }">
    <div class="details-key-value__label">
      {{ label }}:
    </div>
    <div class="details-key-value__value">
      <slot>
        {{ value }}
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
      type: String as PropType<string | null>,
      required: false,
      default: null,
    },
    stacked: {
      type: Boolean,
      required: false,
    },
  })
</script>

<style lang="scss">
.details-key-value {
  display: flex;
  gap: 2px;
  white-space: nowrap;
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

.details-key-value--stacked {
  flex-direction: column;

  .details-key-value__label {
    color: var(--black);
    font-weight: bold;
  }

  .details-key-value__value {
    color: var(--grey-60);
  }
}
</style>
