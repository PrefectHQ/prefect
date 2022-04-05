import axios, { AxiosError } from 'axios'
import { Require } from '@/types/utilities'

export type ExistingHandleError = {
  detail: string,
}


export function isExistingHandleError(error: unknown): error is Require<AxiosError<ExistingHandleError>, 'response'> {
  if (axios.isAxiosError(error)) {
    return error.response?.data.detail !== undefined
  }
  return false
}
