export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  timestamp: string
}

export interface PaginatedData<T> {
  items: T[]
  pagination: {
    page: number
    page_size: number
    total: number
    pages: number
  }
}

export interface PaginatedResponse<T> extends ApiResponse<PaginatedData<T>> {}
