<template>
  <v-container class="fill-height" fluid justify-center>
    <v-layout align-content-start fill-height wrap style="max-width: 1440px;">
      <v-flex xs12>
        <slot name="first-row" />
      </v-flex>
      <v-flex sm12 md8>
        <v-layout wrap>
          <v-flex xs12 sm6>
            <slot name="tile1" />
          </v-flex>
          <v-flex xs12 sm6>
            <slot name="tile2" />
          </v-flex>
          <v-flex xs12 sm12>
            <slot name="table" />
          </v-flex>
        </v-layout>
      </v-flex>
      <v-flex sm12 md4>
        <slot name="activityBar" />
      </v-flex>
    </v-layout>
  </v-container>
</template>
