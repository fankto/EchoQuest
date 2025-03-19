import axios, { type AxiosError, type AxiosRequestConfig, type AxiosResponse } from 'axios'

// Define base API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Create axios instance
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

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
          window.location.href = '/auth/login'
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
        window.location.href = '/auth/login'
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
  data?: Record<string, unknown> | string,
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
      let message = 'An error occurred'
      
      if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        if (error.response.status === 422) {
          // Validation error
          const validationErrors = error.response.data?.detail || error.response.data
          if (typeof validationErrors === 'string') {
            message = validationErrors
          } else if (validationErrors && typeof validationErrors === 'object') {
            // Format validation errors
            const errorMessages = []
            for (const [field, errors] of Object.entries(validationErrors)) {
              if (Array.isArray(errors)) {
                errorMessages.push(`${field}: ${errors.join(', ')}`)
              } else if (typeof errors === 'object' && errors !== null) {
                // Handle nested objects
                errorMessages.push(`${field}: ${JSON.stringify(errors)}`)
              } else {
                errorMessages.push(`${field}: ${errors}`)
              }
            }
            message = errorMessages.join('; ') || 'Validation error'
          } else {
            message = 'Validation error'
          }
        } else {
          // Other error with response
          message = error.response.data?.detail || 
                   error.response.data?.message ||
                   error.message ||
                   'An error occurred'
        }
      } else if (error.request) {
        // The request was made but no response was received
        message = 'No response from server'
      } else {
        // Something happened in setting up the request
        message = error.message || 'Request setup error'
      }
      
      throw new Error(message)
    }
    
    throw error
  }
}

// API methods
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) => 
    apiRequest<T>('get', url, undefined, config),
  
  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) => {
    // Automatically detect FormData and set the proper headers
    if (typeof window !== 'undefined' && data instanceof FormData) {
      console.log('FormData detected, using appropriate headers');
      return api.upload<T>(url, data, config);
    }
    // Handle URLSearchParams for form-urlencoded data
    if (typeof data === 'string' && config?.headers?.['Content-Type'] === 'application/x-www-form-urlencoded') {
      return apiRequest<T>('post', url, data, config);
    }
    return apiRequest<T>('post', url, data as Record<string, unknown>, config);
  },
  
  put: <T>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig) => 
    apiRequest<T>('put', url, data, config),
  
  patch: <T>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig) => {
    return apiRequest<T>('patch', url, data, config);
  },
  
  delete: <T>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig) => {
    // Create a copy of the config
    const requestConfig: AxiosRequestConfig = { ...config };
    
    // Prepare URL with query parameters
    let finalUrl = url;
    
    // For DELETE requests, we'll explicitly construct the URL with query parameters
    // to ensure they're properly formatted
    if (data && Object.keys(data).length > 0) {
      const queryParams = new URLSearchParams();
      
      // Add each data property as a query parameter
      for (const [key, value] of Object.entries(data)) {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      }
      
      // Append query parameters to URL
      const queryString = queryParams.toString();
      if (queryString) {
        finalUrl = `${url}${url.includes('?') ? '&' : '?'}${queryString}`;
      }
    }
    
    // Don't send data in the body for DELETE requests
    return apiRequest<T>('delete', finalUrl, undefined, requestConfig);
  },
    
  // Special method for handling FormData uploads
  upload: <T>(url: string, formData: FormData, config?: AxiosRequestConfig, method: 'post' | 'patch' = 'post') => {
    console.log(`Using ${method} method for`, url);
    const requestMethod = method === 'post' ? apiClient.post : apiClient.patch;
    return requestMethod<T>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      ...config,
    })
    .then(response => {
      console.log('Upload success for', url);
      return response.data;
    })
    .catch(error => {
      console.error('Upload error for', url, error);
      if (axios.isAxiosError(error)) {
        let message = 'File upload failed';
        
        if (error.response) {
          message = error.response.data?.detail || 
                   error.response.data?.message ||
                   error.message ||
                   'File upload failed';
        } else if (error.request) {
          message = 'No response from server during file upload';
        } else {
          message = error.message || 'File upload setup error';
        }
        
        throw new Error(message);
      }
      throw error;
    });
  },
  
  // Method to get the base API URL
  getBaseUrl: () => API_URL
}

export default api