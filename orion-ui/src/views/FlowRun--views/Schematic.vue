<template>
  <Card class="schematic d-flex flex-column" width="auto" shadow="sm">
    <div class="schematic-content pa-2 d-flex flex-grow-1">
      <div
        style="
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          position: absolute;
        "
        class="text-center d-flex align-center"
      >
        <i class="pi pi-tools-fill pi-2x" />
        <h1 class="mx-2">Under construction</h1>
        <i class="pi pi-tools-fill pi-2x" />
      </div>
    </div>
  </Card>
</template>

<script lang="ts" setup></script>

<style lang="scss" scoped>
@use '@/styles/views/flow-run/schematic.scss';
</style>
