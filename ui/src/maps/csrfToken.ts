import { CsrfToken } from "@/models/CsrfToken"
import { CsrfTokenResponse } from "@/types/csrfTokenResponse"

export const mapCsrfTokenResponseToCsrfToken = (response: CsrfTokenResponse): CsrfToken => {
    return {
        token: response.token,
        expiration: new Date(response.expiration),
        issued: new Date(),
    }
}

