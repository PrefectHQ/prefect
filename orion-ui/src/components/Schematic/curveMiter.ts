class Turn {
  _context: any
  _point: number = 0
  _x: number = 0
  _y: number = 0

  lineStart() {
    this._point = 0
    this._x = this._y = 0
  }

  lineEnd(): void {
    return
  }

  /*
  1: Line to 50 away from start
  2: Arc
  3: Line to 50 away from end
  4: Arc
  5: Line to end
*/
  point(x: number, y: number) {
    x = +x
    y = +y

    switch (this._point) {
      case 0:
        this._point = 1
        this._context.moveTo(x, y)
        break
      case 1:
      default:
        this._point = 2
        if (isDiagonal(this._x, this._y, x, y)) {
          const to = interpolateQuadraticArcPoints(this._x, this._y, x, y)
          this._context.lineTo(...to[0])
          this._context.lineTo(...to[1], 5)
          this._context.lineTo(...to[2])
          this._context.lineTo(...to[3], 5)
        }
        this._context.lineTo(x, y)
        break
    }

    this._x = x
    this._y = y
  }

  constructor(context: any) {
    this._context = context
  }
}

export function isDiagonal(
  x1: number,
  y1: number,
  x2: number,
  y2: number
): boolean {
  return x2 !== x1 && y2 !== y1
}

export function direction(
  x1: number,
  y1: number,
  x2: number,
  y2: number
): number {
  return x2 - x1
}

export function makeQuadraticBezierPoints(
  x1: number,
  y1: number,
  x2: number,
  y2: number
): [number, number][] {
  let py1 = 0,
    py2 = 0

  const dy = y2 - y1,
    dist = 50

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

export function interpolateQuadraticArcPoints(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  r: number = 20
): number[][] {
  let py1 = 0,
    py2 = 0,
    ax1 = 0,
    ax2 = 0,
    ap1 = 0,
    ap2 = 0

  const dy = y2 - y1,
    dx = x2 - x1,
    dist = 50

  if (dy > 0) {
    py1 = y1 + dist - r
    py2 = y2 - dist + r

    ap1 = py1 + r
    ap2 = py2 - r
  } else {
    py1 = y1 - dist + r
    py2 = y2 + dist - r

    ap1 = py1 - r
    ap2 = py2 + r
  }

  if (dx > 0) {
    ax1 = x1 - r
    ax2 = x2 + r
  } else {
    ax1 = x1 + r
    ax2 = x2 - r
  }

  return [
    [x1, py1],
    [ax1, ap1],
    [x2, py2],
    [ax2, ap2]
  ]
}

export const curveMiter = function (context: any): Turn {
  return new Turn(context)
}
