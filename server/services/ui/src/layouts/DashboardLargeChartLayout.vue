<template>
  <v-container class="fill-height" fluid justify-center>
    <v-layout align-content-start fill-height wrap style="max-width: 1440px;">
      <v-flex xs12>
        <slot name="firstRow" />
      </v-flex>
      <v-flex sm12 md4>
        <v-layout column>
          <v-flex xs12>
            <slot name="tile1" />
          </v-flex>
          <v-flex xs12>
            <slot name="activityBar" />
          </v-flex>
        </v-layout>
      </v-flex>
      <v-flex sm12 md8 class="pa-2">
        <slot name="chart" />
      </v-flex>
    </v-layout>
  </v-container>
</template>
