function Turn(context) {
  this._context = context
}

export function isDiagonal(x1, y1, x2, y2) {
  return x2 !== x1 && y2 !== y1
}

export function makeQuadraticBezierPoints(x1, y1, x2, y2) {
  const turnDist = 0.3

  let py1 = 0,
    py2 = 0,
    dy = y2 - y1,
    dist = Math.abs(dy) * turnDist

  if (dy > 0) {
    py1 = y1 + dist
    py2 = y2 - dist
  } else {
    py1 = y1 - dist
    py2 = y2 + dist
  }

  return [
    [x1, py1],
    [x2, py2]
  ]
}

Turn.prototype = {
  lineStart: function() {
    this._point = 0
    this._x = this._y = null
  },
  lineEnd: function() {},
  point: function(x, y) {
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

export const curveMetro = function(context) {
  return new Turn(context)
}
