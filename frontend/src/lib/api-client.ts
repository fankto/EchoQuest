import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios'

// Define base API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Create axios instance
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    // Get token from local storage
    const token = localStorage.getItem('token')
    
    // Add auth header if token exists
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    return config
  },
  (error) => Promise.reject(error)
)

// Add interceptor for handling token expiration
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean }
    
    // If 401 error and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      
      try {
        // Get refresh token
        const refreshToken = localStorage.getItem('refreshToken')
        
        if (!refreshToken) {
          // No refresh token, logout
          localStorage.removeItem('token')
          localStorage.removeItem('refreshToken')
          window.location.href = '/login'
          return Promise.reject(error)
        }
        
        // Call refresh token endpoint
        const response = await axios.post(`${API_URL}/api/auth/refresh`, {
          refresh_token: refreshToken,
        })
        
        // Update tokens
        const { access_token, refresh_token } = response.data
        localStorage.setItem('token', access_token)
        localStorage.setItem('refreshToken', refresh_token)
        
        // Update auth header for original request
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`
        }
        
        // Retry original request
        return apiClient(originalRequest)
      } catch (refreshError) {
        // Refresh failed, logout
        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }
    
    return Promise.reject(error)
  }
)

// Generic API request function
export const apiRequest = async <T>(
  method: string,
  url: string,
  data?: any,
  config?: AxiosRequestConfig
): Promise<T> => {
  try {
    const response: AxiosResponse<T> = await apiClient({
      method,
      url,
      data,
      ...config,
    })
    
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      // Handle API errors
      const message = 
        error.response?.data?.detail ||
        error.message ||
        'An error occurred'
      
      throw new Error(message)
    }
    
    throw error
  }
}

// API methods
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) => 
    apiRequest<T>('get', url, undefined, config),
  
  post: <T>(url: string, data?: any, config?: AxiosRequestConfig) => 
    apiRequest<T>('post', url, data, config),
  
  put: <T>(url: string, data?: any, config?: AxiosRequestConfig) => 
    apiRequest<T>('put', url, data, config),
  
  patch: <T>(url: string, data?: any, config?: AxiosRequestConfig) => 
    apiRequest<T>('patch', url, data, config),
  
  delete: <T>(url: string, config?: AxiosRequestConfig) => 
    apiRequest<T>('delete', url, undefined, config),
}

export default api