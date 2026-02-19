import { useEffect, useState } from 'react'

export interface AuditLog {
  id: string
  action: string
  details: string
  entityId?: string
  entityType?: string
  timestamp: string
  ipAddress?: string
}

export interface PagedResult<T> {
  items: T[]
  total: number
}

// Minimal stub hook to satisfy UI; returns empty data by default.
export function useUserAuditLogs(_params: Record<string, any>) {
  const [data, setData] = useState<PagedResult<AuditLog>>({ items: [], total: 0 })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    // In a real app, fetch from API here.
    setIsLoading(false)
    setError(null)
    setData({ items: [], total: 0 })
  }, [JSON.stringify(_params)])

  return { data, isLoading, error }
}
