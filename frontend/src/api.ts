export type Item = {
  id: number
  code: string
  name: string
  unit: string
  description: string | null
  image_path: string | null
  active: boolean
  quantity_available: number
  minimum_stock: number
}

export type ItemCreate = {
  code: string
  name: string
  unit: string
  description?: string | null
  minimum_stock: number
}

export type ItemUpdate = {
  code: string
  name: string
  unit: string
  description: string | null
  active: boolean
  minimum_stock: number
}

export type StockMovementCreate = {
  quantity: number
  note?: string
}

export type StockMovement = {
  id: number
  item_id: number
  movement_type: 'IN' | 'OUT'
  quantity: number
  occurred_at: string
  note: string | null
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export function itemImageUrl(item: Pick<Item, 'id' | 'image_path'>) {
  if (!item.image_path) return null
  return `${apiBaseUrl}/items/${item.id}/image?v=${encodeURIComponent(item.image_path)}`
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      headers: {
        ...(options?.body && !(options.body instanceof FormData)
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...options?.headers,
      },
    })
  } catch {
    throw new Error('No se pudo conectar con la API. Comprueba que esté en marcha.')
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new Error(readApiError(body, response.status))
  }
  return response.json() as Promise<T>
}

function readApiError(body: unknown, status: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = body.detail
    if (typeof detail === 'string') {
      const normalized = detail.toLowerCase()
      if (normalized.includes('insufficient')) {
        return 'No hay cantidad suficiente para registrar esa salida.'
      }
      if (normalized.includes('inactive')) {
        return 'No se pueden registrar movimientos en un artículo inactivo.'
      }
      if (normalized.includes('already exists')) {
        return 'Ya existe un artículo con ese código.'
      }
      if (normalized.includes('not found')) {
        return 'El artículo ya no existe. Actualiza la lista.'
      }
      if (normalized.includes('exceeds') || normalized.includes('too large')) {
        return 'La imagen supera el tamaño permitido.'
      }
      if (normalized.includes('image') || normalized.includes('format')) {
        return 'El archivo no es una imagen válida. Usa JPEG, PNG, WebP o GIF.'
      }
      return detail
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => {
          if (typeof entry === 'object' && entry !== null && 'msg' in entry) {
            return String(entry.msg)
          }
          return ''
        })
        .filter(Boolean)
      return messages.length
        ? `Revisa los datos introducidos: ${messages.join('; ')}`
        : 'Los datos enviados no son válidos.'
    }
  }
  return `La API respondió con un error (${status}).`
}

export function getItems() {
  return request<Item[]>('/items/')
}

export function createItem(item: ItemCreate) {
  return request<Item>('/items/', {
    method: 'POST',
    body: JSON.stringify(item),
  })
}

export function getItem(itemId: number) {
  return request<Item>(`/items/${itemId}`)
}

export function updateItem(itemId: number, item: ItemUpdate) {
  return request<Item>(`/items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(item),
  })
}

export function getItemMovements(itemId: number, offset = 0, limit = 50) {
  return request<StockMovement[]>(
    `/items/${itemId}/movements?limit=${limit}&offset=${offset}`,
  )
}

export function uploadItemImage(itemId: number, file: File) {
  const data = new FormData()
  data.append('image', file)
  return request<Item>(`/items/${itemId}/image`, {
    method: 'POST',
    body: data,
  })
}

export function registerMovement(
  itemId: number,
  direction: 'in' | 'out',
  movement: StockMovementCreate,
) {
  return request<StockMovement>(`/items/${itemId}/movements/${direction}`, {
    method: 'POST',
    body: JSON.stringify(movement),
  })
}
