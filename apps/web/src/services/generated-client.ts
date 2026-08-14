import createClient from 'openapi-fetch'

import type { paths } from '@/generated/api'

const apiBase = import.meta.env.VITE_API_BASE ?? '/api/v1'
const clientBase = apiBase.endsWith('/api/v1') ? apiBase.slice(0, -'/api/v1'.length) : apiBase

let accessToken = ''

export function setGeneratedAccessToken(token: string) {
  accessToken = token
}

export const generatedClient = createClient<paths>({
  baseUrl: clientBase || '/',
  credentials: 'include',
  fetch: async (request) => {
    const headers = new Headers(request.headers)
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    return fetch(new Request(request, { headers, credentials: 'include' }))
  },
})
