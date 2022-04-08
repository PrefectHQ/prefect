import { ref } from 'vue'

const storageKey = 'orion-color-mode'

export const colorModes = [
  'default',
  'achromatomaly',
  'achromatopsia',
  'protanomaly',
  'protaponia',
  'deuteranomaly',
  'deuteranopia',
  'tritanomaly',
  'tritanopia',
] as const

export type ColorMode = typeof colorModes[number]
export type ColorModeClass = `${ColorMode}-color-mode`

export const colorMode = ref<ColorMode>(getColorMode())

function getColorMode(): ColorMode {
  const defaultMode = 'default'

  try {
    const fromLocalStorage = localStorage.getItem(storageKey) as ColorMode | undefined

    return fromLocalStorage ?? 'default'
  } catch (err) {
    console.warn(err)
  }

  return defaultMode
}

export function setColorMode(value: ColorMode): void {
  localStorage.setItem(storageKey, value)
  colorMode.value = value

  applyColorMode()
}

export function applyColorMode(): void {
  const currentColorMode = `${ getColorMode() }-color-mode`

  colorModes.forEach(colorMode => {
    document.body.classList.remove(`${colorMode}-color-mode`)
  })

  document.body.classList.add(currentColorMode)
}