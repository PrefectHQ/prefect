<template>
  <div class="navbar" tabindex="-1">
    <div class="nav-item">
      <router-link to="/">
        <i class="material-icons">home</i>
      </router-link>
    </div>
    <div class="nav-item">
      <router-link to="/schematics">
        <i class="material-icons">bubble_chart</i>
      </router-link>
    </div>
  </div>
</template>

<script lang="ts">
import { Vue } from 'vue-class-component'

export default class NavBar extends Vue {}
</script>

<style scoped lang="scss">
.navbar {
  background-color: #fff;
  box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.06), 0px 4px 6px rgba(0, 0, 0, 0.1);
  height: 100vh;
  max-width: 100px;
  padding-top: 8px;
  position: relative;
  transition: max-width 150ms ease-in-out 150ms;
  top: 0;
  z-index: 10;

  .nav-item {
    align-content: center;
    display: flex;
    justify-content: center;
    margin-top: 16px;
    margin-bottom: 16px;
    transition: width 150ms ease-in-out 150ms;
    width: 50px;
  }
}
</style>
