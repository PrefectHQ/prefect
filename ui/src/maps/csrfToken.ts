import { CsrfToken } from '@/models/CsrfToken'
import { MapFunction } from '@/services/mapper'
import { CsrfTokenResponse } from '@/types/csrfTokenResponse'

export const mapCsrfTokenResponseToCsrfToken: MapFunction<CsrfTokenResponse, CsrfToken> = function(source) {
  return {
    token: source.token,
    expiration: this.map('string', source.expiration, 'Date'),
    issued: new Date(),
  }
}

