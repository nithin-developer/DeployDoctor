/**
 * Utility to clean up conflicting authentication data
 * This helps resolve issues where multiple auth systems or old data might conflict
 */

const CONFLICTING_AUTH_KEYS = [
  'auth-storage',
  'clerk-db',
  'clerk-state', 
  'clerk-session',
  'clerk-user',
  // Add other potential conflicting keys here
]

/**
 * Clean up any conflicting auth data while preserving the main healthcare auth
 */
export function cleanupConflictingAuthData(): void {
  try {
    // Get current healthcare auth data
    const currentToken = localStorage.getItem('healthcare_auth_token')
    const currentUser = localStorage.getItem('healthcare_auth_user')
    
    console.log('Cleaning up conflicting auth data...')
    
    // Remove conflicting auth systems
    CONFLICTING_AUTH_KEYS.forEach(key => {
      if (localStorage.getItem(key)) {
        console.log(`Removing conflicting auth data: ${key}`)
        localStorage.removeItem(key)
      }
    })
    
    // If we have valid healthcare auth, log it
    if (currentToken && currentUser) {
      try {
        const user = JSON.parse(currentUser)
        console.log(`Healthcare auth preserved for user: ${user.email} (${user.role})`)
      } catch (e) {
        console.warn('Could not parse user data:', e)
      }
    }
    
    console.log('Auth cleanup completed')
  } catch (error) {
    console.warn('Error during auth cleanup:', error)
  }
}

/**
 * Check if there are conflicting auth systems active
 */
export function hasConflictingAuthData(): boolean {
  try {
    return CONFLICTING_AUTH_KEYS.some(key => localStorage.getItem(key) !== null)
  } catch (error) {
    console.warn('Error checking for conflicting auth data:', error)
    return false
  }
}

/**
 * Get summary of current auth state for debugging
 */
export function getAuthSummary(): { [key: string]: any } {
  try {
    const summary: { [key: string]: any } = {}
    
    // Check healthcare auth
    const token = localStorage.getItem('healthcare_auth_token')
    const userStr = localStorage.getItem('healthcare_auth_user')
    
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr)
        summary.healthcare = {
          hasToken: !!token,
          user: {
            email: user.email,
            role: user.role,
            exp: new Date(user.exp).toISOString(),
            expired: Date.now() > user.exp
          }
        }
      } catch (e) {
        summary.healthcare = { hasToken: !!token, userParseError: true }
      }
    }
    
    // Check for conflicting systems
    CONFLICTING_AUTH_KEYS.forEach(key => {
      const data = localStorage.getItem(key)
      if (data) {
        summary.conflicting = summary.conflicting || {}
        summary.conflicting[key] = data.length > 100 ? `${data.substring(0, 100)}...` : data
      }
    })
    
    return summary
  } catch (error: any) {
    return { error: error?.message || 'Unknown error' }
  }
}
