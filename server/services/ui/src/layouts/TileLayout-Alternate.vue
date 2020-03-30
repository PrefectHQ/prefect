<template>
  <v-container fluid style="max-width: 1440px;" class="mx-auto pt-0 px-3 pb-12">
    <v-row>
      <v-col cols="12" md="4" class="py-0">
        <v-row v-if="$slots['col-1-tile-1']" class="justify-start">
          <v-col class="pb-0">
            <v-row>
              <v-col>
                <slot name="col-1-tile-1" />
              </v-col>
            </v-row>
          </v-col>
        </v-row>

        <v-row v-if="$slots['col-1-tile-2']" class="justify-start">
          <v-col class="pt-0">
            <v-row>
              <v-col>
                <slot name="col-1-tile-2" />
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </v-col>

      <v-col cols="12" md="8" class="py-0">
        <v-row v-if="$slots['actions-row']" class="justify-start">
          <v-col
            :class="
              $slots['row-1-tile-1'] || $slots['row-1-tile-2'] ? 'pb-0' : ''
            "
          >
            <v-row>
              <v-col>
                <slot name="actions-row" />
              </v-col>
            </v-row>
          </v-col>
        </v-row>

        <v-row
          v-if="$slots['row-1-tile-1'] || $slots['row-1-tile-2']"
          class="justify-start"
        >
          <v-col
            :class="
              $slots['row-2-tile-1'] || $slots['row-2-tile-2']
                ? $slots['actions-row']
                  ? 'py-0'
                  : 'pb-0'
                : $slots['actions-row']
                ? 'pt-0'
                : ''
            "
          >
            <v-row style="height: 351px;">
              <v-col>
                <slot name="row-1-tile-1" />
              </v-col>
              <v-col>
                <slot name="row-1-tile-2" />
              </v-col>
            </v-row>
          </v-col>
        </v-row>

        <v-row
          v-if="$slots['row-2-tile-1'] || $slots['row-2-tile-2']"
          class="justify-start"
        >
          <v-col
            :class="
              $slots['row-1-tile-1'] || $slots['row-1-tile-2'] ? 'pt-0' : ''
            "
          >
            <v-row style="height: 351px;">
              <v-col v-if="$slots['row-2-tile-1']">
                <slot name="row-2-tile-1" />
              </v-col>
              <v-col v-if="$slots['row-2-tile-2']">
                <slot name="row-2-tile-2" />
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </v-col>
    </v-row>
  </v-container>
</template>
