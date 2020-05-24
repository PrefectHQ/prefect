export function Tree(tree) {
  this.tree = tree
  this.arr = []
  this.mapping = {}

  this.inOrder(this.tree)

  this.height = this.calcHeight()
  this.width = this.calcWidth()
}

Tree.prototype.inOrder = function(node, row = 0) {
  if (node == null) return
  let _row = row

  if (!this.mapping[node.id] && node.id) {
    _row = row + 1

    this.arr[row]
      ? this.arr[row].push(node.children.length)
      : (this.arr[row] = [node.children.length])

    this.mapping[node.id] = true
  }

  for (let i = 0; i < node.children.length; ++i) {
    this.inOrder(node.children[i], _row)
  }
}

Tree.prototype.calcWidth = function() {
  let height = 0
  for (let i = 0; i < this.arr.length; ++i) {
    height = this.arr[i].length > height ? this.arr[i].length : height
  }
  return height
}

Tree.prototype.calcHeight = function() {
  return this.arr.length
}
