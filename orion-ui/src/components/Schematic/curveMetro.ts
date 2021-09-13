// @ts-nocheck
function Turn(context) {
  this._context = context
}

export function isDiagonal(x1: number, y1: number, x2: number, y2: number) {
  return x2 !== x1 && y2 !== y1
}

function direction(z1: number, z2: number, d: number, c: number) {
  let n1 = 0,
    n2 = 0
  if (d > 0) {
    n1 = z1 + c
    n2 = z2 - c
  } else {
    n1 = z1 - c
    n2 = z2 + c
  }
  return [n1, n2]
}

export function makeQuadraticBezierPoints(
  x1: number,
  y1: number,
  x2: number,
  y2: number
) {
  let dx = x2 - x1,
    dy = y2 - y1

  let [px1, px2] = direction(x1, x2, dx, 125)
  let [py1, py2] = direction(y1, y2, dy, 50)

  if (dx < dy) {
    if ((dx > 0 && px1 > px2) || (dx < 0 && px1 < px2)) {
      return [
        [x1, py1],
        [x2, py2]
      ]
    } else {
      return [
        [px1, y1],
        [px2, y2]
      ]
    }
  }

  if (dx > dy) {
    if ((dy > 0 && py1 > py2) || (dy < 0 && py1 < py2)) {
      return [
        [px1, y1],
        [px2, y2]
      ]
    } else {
      return [
        [x1, py1],
        [x2, py2]
      ]
    }
  }
}

Turn.prototype = {
  lineStart: function () {
    this._point = 0
    this._x = this._y = null
  },
  lineEnd: function () {},
  point: function (x: number, y: number) {
    x = +x
    y = +y

    switch (this._point) {
      case 0:
        this._context.moveTo(x, y)
        this._point = 1
        break
      default:
        this._point = 2
        if (isDiagonal(this._x, this._y, x, y)) {
          let to = makeQuadraticBezierPoints(this._x, this._y, x, y)
          this._context.lineTo(...to[0])
          this._context.lineTo(...to[1])
        }
        this._context.lineTo(x, y)
        break
    }

    this._x = x
    this._y = y
  }
}

export const curveMetro = function (context) {
  return new Turn(context)
}
