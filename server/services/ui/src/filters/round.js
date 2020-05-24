import round from 'lodash.round'

export function roundWhole(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundWhole filter requires a number instead.`
    )
    return x
  }

  return round(x)
}

export function roundTenths(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundTenths filter requires a number instead.`
    )
    return x
  }

  return round(x, 1)
}

export function roundHundredths(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundHundredths filter requires a number instead.`
    )
    return x
  }

  return round(x, 2)
}

export function roundThousandths(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundThousandths filter requires a number instead.`
    )
    return x
  }

  return round(x, 3)
}

export function roundTens(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundTens filter requires a number instead.`
    )
    return x
  }

  return round(x, -1)
}

export function roundHundreds(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundHundreds filter requires a number instead.`
    )
    return x
  }

  return round(x, -2)
}

export function roundThousands(x) {
  if (!x || typeof x !== 'number') {
    // eslint-disable-next-line no-console
    console.warn(
      `Value ${x} is a ${typeof x}, roundThousands filter requires a number instead.`
    )
    return x
  }

  return round(x, 3)
}
