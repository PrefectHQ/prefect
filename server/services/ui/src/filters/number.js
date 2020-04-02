import numeral from 'numeral'

export default function(number) {
  return numeral(number).format('0,0')
}
