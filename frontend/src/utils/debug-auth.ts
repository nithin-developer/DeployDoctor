/**
 * Debug utilities for authentication issues
 */

import { useAuthStore } from '@/stores/authStore'
import { cleanupConflictingAuthData, getAuthSummary } from './auth-cleanup'

/**
 * Debug function to check current auth state
 * Call this from browser console: window.debugAuth()
 */
export function debugAuth() {
  const authStore = useAuthStore.getState()
  
  console.log('=== AUTH DEBUG INFO ===')
  console.log('Current auth state:', {
    isAuthenticated: authStore.auth.isAuthenticated(),
    hasUser: !!authStore.auth.user,
    hasToken: !!authStore.auth.accessToken,
    user: authStore.auth.user ? {
      id: authStore.auth.user.id,
      email: authStore.auth.user.email,
    } : null,
    expiresAt: authStore.auth.expiresAt ? new Date(authStore.auth.expiresAt).toISOString() : null,
    expired: authStore.auth.expiresAt ? Date.now() > authStore.auth.expiresAt : null
  })
  
  console.log('Local storage auth data:', {
    token: localStorage.getItem('healthcare_auth_token'),
    user: localStorage.getItem('healthcare_auth_user')
  })
  
  console.log('Auth summary:', getAuthSummary())
  
  console.log('All localStorage auth keys:')
  Object.keys(localStorage).forEach(key => {
    if (key.includes('auth') || key.includes('token') || key.includes('user') || key.includes('clerk')) {
      const value = localStorage.getItem(key)
      console.log(`  ${key}: ${value?.substring(0, 100)}${(value?.length || 0) > 100 ? '...' : ''}`)
    }
  })
  console.log('======================')
}

/**
 * Force reload auth from localStorage
 */
export function reloadAuth() {
  console.log('Auth state is persisted automatically by the store; no explicit reload needed.')
}

/**
 * Clear all auth data and start fresh
 */
export function clearAllAuth() {
  console.log('Clearing all auth data...')
  
  // Clear specific healthcare auth
  localStorage.removeItem('healthcare_auth_token')
  localStorage.removeItem('healthcare_auth_user')
  
  // Clear conflicting auth data
  cleanupConflictingAuthData()
  
  // Reset store
  useAuthStore.getState().auth.reset()
  
  console.log('Auth cleared. Please refresh the page.')
}

// Make functions available globally for debugging
if (typeof window !== 'undefined') {
  ;(window as any).debugAuth = debugAuth
  ;(window as any).reloadAuth = reloadAuth  
  ;(window as any).clearAllAuth = clearAllAuth
}
