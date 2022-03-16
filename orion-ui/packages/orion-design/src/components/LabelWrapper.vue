<template>
  <div class="label-wrapper">
    <sup class="label-wrapper__super">
      {{ label }}
    </sup>
    <slot />
  </div>
</template>

<script lang="ts" setup >
  defineProps<{ label: string }>()
</script>

<style lang="scss">
.label-wrapper {
  margin-top: 15px;
  width: 100%;
}

.label-wrapper__super {
  display: block;
  font-size: 13px;
  font-family: "input-sans";
  line-height: 18px;
  letter-spacing: -.09px;
  font-weight: 600;
}
</style>