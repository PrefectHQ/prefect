<template>
  <m-card shadow="sm">
    <div class="create-workspace-card">
      <div class="create-workspace-card__background-image" />
      <div class="create-workspace-card__text">
        <h1>{{header}}</h1>
        <span>{{description}}</span>
        <router-link :to="link">
          <m-button color="primary" miter icon="pi-add-line">
            {{buttonText}}
          </m-button>
        </router-link>
      </div>
      <img :src="imagePath" alt="imageAltText" class="create-workspace-card__card-image">
    </div>
  </m-card>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
    name: 'EmptyStateCard',
    props: {
      buttonText: {
        type: String,
        required: true,
      },
      header: {
        type: String,
        required: true,
      },
      description: {
        type: String,
        required: true,
      },
      link: {
        type:String,
        required: true
      },
      imagePath: {
        type: String,
        required: true,
      },
      imageAltText: {
        type: String,
        required: true,
      }
    }
    })

</script>

<style lang="scss" scoped>


@mixin breakpoint($breakpoint) {
    @if $breakpoint == sm {
      @media only screen and (min-width: 640px) {
        @content;
      }
    }
    @if $breakpoint == lg {
      @media only screen and (min-width: 1024px) {
        @content;
      }
    }
  }

.create-workspace-card {
  display: flex;
  flex-direction: column;
  text-align: center;
  position: relative;
  overflow: hidden;
  padding: 20px;

  @include breakpoint(lg) {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    height: 380px;
    padding: 0 80px;
  }

  &__text {
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    position: relative;
    z-index: 1000;
    margin-bottom: 15px;

    * {
      margin: 8px 0;
      letter-spacing: 0;
    }

    @include breakpoint(lg) {
      text-align: left;
      margin-right: 50px;
      margin-bottom: 0;
      min-width: 250px;
      align-items: flex-start;
    }
  }

  &__card-image {
    position: relative;
    max-height: 235px;
    display: none;

    @include breakpoint(sm) {
      display: inline-block;
    }
  }

  &__background-image {
    background-image: url("/images/circle.svg");
    background-size: contain;
    background-repeat: no-repeat;
    height: 1500px;
    width: 1500px;
    top: -150px;
    left: 10vw;
    position: absolute;
    animation: create-workspace-card-rotate 40s infinite linear;

    @include breakpoint(md) {
      left: 50vw;
    }
   }
}

@keyframes create-workspace-card-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>