import api from '@/api'

export interface AuditLog {
  id: string
  user_id: string | null
  username: string | null
  action: string
  resource: string
  resource_id: string | null
  method: string
  path: string
  ip_address?: string | null
  status_code: number
  detail: string | null
  created_at: string
}

export async function listAuditLogs(params: Record<string, unknown> = {}) {
  const response = await api.get('/audit/logs', { params })
  return response.data.data as {
    items: AuditLog[]
    pagination: { page: number; page_size: number; total: number; pages: number }
  }
}
