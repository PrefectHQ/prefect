export default class Drawer {
  constructor(type, title = null, props = {}) {
    if (!type) {
      throw new Error('Type is a required field')
    }
    this.type = type
    this.title = title
    this.props = props
  }
}
