import { ReactNode } from 'react'
import { useAuth } from '@/stores/authStore'
import { Navigate } from 'react-router-dom'
import { toast } from 'sonner'

interface ProtectedRouteProps {
  children: ReactNode
  requireAuth?: boolean
}

export function ProtectedRoute({ 
  children, 
  requireAuth = true 
}: ProtectedRouteProps) {
  const auth = useAuth()

  // Check if authentication is required and user is not authenticated
  if (requireAuth && !auth.isAuthenticated()) {
    toast.error('Please log in to access this page')
    return <Navigate to={`/sign-in?redirect=${encodeURIComponent(window.location.pathname)}`} replace />
  }

  return <>{children}</>
}
