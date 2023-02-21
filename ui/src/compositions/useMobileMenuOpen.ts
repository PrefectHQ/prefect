import { Ref, ref } from 'vue'

export type UseMobileMenuOpen = {
  mobileMenuOpen: Ref<boolean>,
  open: () => void,
  close: () => void,
  toggle: () => void,
}

export function useMobileMenuOpen(): UseMobileMenuOpen {
  const mobileMenuOpen = ref(false)

  function toggle(): void {
    mobileMenuOpen.value = !mobileMenuOpen.value
  }

  function open(): void {
    mobileMenuOpen.value = true
  }

  function close(): void {
    mobileMenuOpen.value = false
  }

  return {
    mobileMenuOpen,
    open,
    close,
    toggle,
  }
}