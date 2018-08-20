<template>
  <div id=login-container>
    <img id=logo src='/logo.svg' height=300px;>
    <h1>Prefect (Preview)</h1>
    <a v-on:click.prevent="login" id=data-netlify-identity-button href="">Login</a>
  </div>
</template>

<script>
const netlifyIdentity = require("netlify-identity-widget");

export default {
  methods: {
    login () {
        netlifyIdentity.open('login')
    }
  }
}

</script>

<style lang="stylus">

$accentColor = #20a0ff

#login-container
  display flex
  flex-direction column
  align-content center
  align-items center

#logo
  margin-top 100px
  margin-bottom 50px

#login-button, #data-netlify-identity-button
  margin-top: 40px
  display inline-block
  font-size 1.2rem
  color #fff
  background-color $accentColor
  padding 0.8rem 1.6rem
  border-radius 4px
  transition background-color .1s ease
  box-sizing border-box
  border-bottom 1px solid darken($accentColor, 10%)
  &:hover
    background-color lighten($accentColor, 10%)
</style>
