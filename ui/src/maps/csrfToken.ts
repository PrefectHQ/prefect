import { CsrfToken } from "@/models/CsrfToken"
import { CsrfTokenResponse } from "@/types/csrfTokenResponse"
import { MapFunction } from '@/services/mapper'

export const mapCsrfTokenResponseToCsrfToken: MapFunction<CsrfTokenResponse, CsrfToken> = function(source) {
    return {
        token: source.token,
        expiration: this.map('string', source.expiration, 'Date'),
        issued: new Date(),
    }
}

