import { mount } from '@vue/test-utils'
import StateColorModeSelector from './StateColorModeSelector.vue'

const colorModes = [
  'Default',
  'Achromatomaly',
  'Achromatopsia',
  'Protanomaly',
  'Protaponia',
  'Deuteranomaly',
  'Deuteranopia',
  'Tritanomaly',
  'Tritanopia'
]

const factoryMount = (props = {}, slots = {}) => {
  return mount(StateColorModeSelector, {
    props,
    slots
  })
}

test('component renders options for each color mode', () => {
  const wrapper = factoryMount()
  const options = wrapper.findAll('option')
  const renderedOptions = options.map((option) => option.text())

  expect(colorModes.every((mode) => renderedOptions.includes(mode)))
})

// Will add these when test utils are working properly
// test('color mode is set in local storage', () => {
//   expect()
// })

// test('color mode is retrieved from local storage', () => {
//   expect()
// })
