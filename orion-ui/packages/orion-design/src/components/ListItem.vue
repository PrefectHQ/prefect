<template>
  <div class="list-item">
    <slot />
  </div>
</template>


<style lang="scss">
.list-item {
  background-color: var(--white);
  filter: drop-shadow(0px 1px 2px rgba(0, 0, 0, 0.06))
          drop-shadow(0px 1px 3px rgba(0, 0, 0, 0.1));
  padding: var(--p-1) var(--p-2);

  &:first-of-type {
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
  }

  &:not(:first-of-type) {
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;

    border-top: 1px solid $secondary-hover;
  }

  &:last-of-type {
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
  }
}
</style>
