<template>
  <m-card shadow="sm">
    <div class="empty-state-card">
      <div class="empty-state-card__background-image" />
      <div class="empty-state-card__text">
        <h1 class="empty-state-card__letters">{{header}}</h1>
        <p class="empty-state-card__letters">{{description}}</p>
        <router-link :to="link">
          <m-button color="primary" miter icon="pi-add-line">
            {{buttonText}}
          </m-button>
        </router-link>
      </div>
      <img :src="imagePath" alt="imageAltText" class="empty-state-card__card-image">
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

<style lang="scss">
@use 'sass:map';
.empty-state-card {
  display: flex;
  flex-direction: column;
  text-align: center;
  position: relative;
  overflow: hidden;
  padding: 20px;

@media only screen and (min-width: map.get($breakpoints, 'lg')) {
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


    @media only screen and (min-width: map.get($breakpoints, 'lg')) {
      text-align: left;
      margin-right: 50px;
      margin-bottom: 0;
      min-width: 250px;
      align-items: flex-start;
    }
  }
  
  &__letters {
      gap: 8px 0;
      letter-spacing: 0;
    }

  &__card-image {
    position: relative;
    max-height: 235px;
    display: none;

    @media only screen and (min-width: map.get($breakpoints, 'sm')) {
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
    animation: empty-state-card-rotate 40s infinite linear;

    @media only screen and (min-width: map.get($breakpoints, 'md')) {
      left: 50vw;
    }
   }
}

@keyframes empty-state-card-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>