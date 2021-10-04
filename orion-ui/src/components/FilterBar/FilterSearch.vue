<template>
  <div
    class="
      search-input
      px-2
      flex-grow-1 flex-shrink-0
      d-flex
      align-center
      font--primary
      justify-space-between
    "
  >
    <i class="pi pi-search-line mr-1" />
    <!-- <input v-model="search" class="flex-grow-1" placeholder="Search..." />
    <div class="flex-grow-1">
     
      
    </div> -->
    <div class="d-flex"> <slot /> </div>
  </div>
</template>

<script lang="ts" setup></script>
