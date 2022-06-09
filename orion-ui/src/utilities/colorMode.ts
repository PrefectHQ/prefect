import { applyColorModeClass, ColorMode, defaultColorMode, isColorMode } from '@prefecthq/orion-design'

const colorModeLocalStorageKey = 'orion-color-mode'

export function getActiveColorMode(): ColorMode {
  try {
    const fromLocalStorage = localStorage.getItem(colorModeLocalStorageKey)

    if (isColorMode(fromLocalStorage)) {
      return fromLocalStorage
    }
  } catch (err) {
    console.warn(err)
  }

  return defaultColorMode
}

export function setActiveColorMode(value: ColorMode): void {
  try {
    localStorage.setItem(colorModeLocalStorageKey, value)
  } catch (err) {
    console.warn(err)
  }

  applyActiveColorModeClass()
}

export function applyActiveColorModeClass(): void {
  const active = getActiveColorMode()

  applyColorModeClass(active)
}