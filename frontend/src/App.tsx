import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  createItem,
  getItems,
  registerMovement,
  type Item,
} from './api'
import ItemDetailModal from './ItemDetailModal'
import './App.css'

type MovementDirection = 'in' | 'out'

function stockStatus(item: Item) {
  if (item.quantity_available === 0) return { label: 'Sin stock', className: 'empty' }
  if (item.quantity_available <= item.minimum_stock) {
    return { label: 'Stock bajo', className: 'low' }
  }
  return { label: 'Stock suficiente', className: 'good' }
}

function App() {
  const [items, setItems] = useState<Item[]>([])
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [activeMovement, setActiveMovement] = useState<{
    itemId: number
    direction: MovementDirection
  } | null>(null)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const loadItems = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setLoadError('')
    try {
      const freshItems = await getItems()
      setItems(freshItems)
      setSelectedItem((current) =>
        current ? freshItems.find(({ id }) => id === current.id) ?? current : null,
      )
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'No se pudo cargar el inventario.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const syncItem = useCallback((updated: Item) => {
    setItems((current) => current.map((entry) => entry.id === updated.id ? updated : entry))
    setSelectedItem(updated)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadItems(), 0)
    return () => window.clearTimeout(timer)
  }, [loadItems])

  const activeItems = useMemo(() => items.filter((item) => item.active), [items])
  const visibleItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('es')
    if (!query) return activeItems
    return activeItems.filter(
      (item) =>
        item.code.toLocaleLowerCase('es').includes(query) ||
        item.name.toLocaleLowerCase('es').includes(query),
    )
  }, [activeItems, search])
  const lowStockCount = activeItems.filter(
    (item) => item.quantity_available <= item.minimum_stock,
  ).length

  async function submitMovement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!activeMovement) return
    const formData = new FormData(event.currentTarget)
    const rawQuantity = String(formData.get('quantity') ?? '')
    const quantity = Number(rawQuantity)
    if (!Number.isSafeInteger(quantity) || quantity <= 0) {
      setActionError('Introduce una cantidad entera mayor que cero.')
      return
    }

    const note = String(formData.get('note') ?? '').trim()
    const item = activeItems.find(({ id }) => id === activeMovement.itemId)
    setSaving(true)
    setActionError('')
    setNotice('')
    try {
      await registerMovement(activeMovement.itemId, activeMovement.direction, {
        quantity,
        ...(note ? { note } : {}),
      })
      setNotice(
        `${activeMovement.direction === 'in' ? 'Entrada' : 'Salida'} registrada para ${item?.name ?? 'el artículo'}.`,
      )
      setActiveMovement(null)
      await loadItems(true)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'No se pudo registrar el movimiento.')
    } finally {
      setSaving(false)
    }
  }

  async function submitNewItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    const code = String(formData.get('code') ?? '').trim()
    const name = String(formData.get('name') ?? '').trim()
    const unit = String(formData.get('unit') ?? '').trim()
    const minimumStock = Number(formData.get('minimum_stock'))
    if (!code || code.length > 50 || !name || name.length > 100 || !unit || unit.length > 20) {
      setCreateError('Completa los campos respetando sus longitudes máximas.')
      return
    }
    if (!Number.isSafeInteger(minimumStock) || minimumStock < 0) {
      setCreateError('El stock mínimo debe ser un número entero igual o mayor que cero.')
      return
    }

    setCreating(true)
    setCreateError('')
    setNotice('')
    try {
      const created = await createItem({ code, name, unit, minimum_stock: minimumStock })
      setNotice(`Artículo ${created.code} creado correctamente.`)
      form.reset()
      await loadItems(true)
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : 'No se pudo crear el artículo.')
    } finally {
      setCreating(false)
    }
  }

  function openMovement(itemId: number, direction: MovementDirection) {
    setActionError('')
    setNotice('')
    setActiveMovement({ itemId, direction })
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#inicio" aria-label="Taller Stock, inicio">
          <span className="brand-mark" aria-hidden="true">TS</span>
          <span><strong>Taller Stock</strong><small>Control de existencias</small></span>
        </a>
        <div className="connection-state"><span /> API de inventario</div>
      </header>

      <section className="page-heading" id="inicio">
        <div>
          <p className="eyebrow">GESTIÓN DEL TALLER</p>
          <h1>Inventario de repuestos</h1>
          <p className="subtitle">Consulta existencias y registra movimientos de forma rápida.</p>
        </div>
        <button
          className="button button-secondary refresh-button"
          type="button"
          onClick={() => void loadItems(true)}
          disabled={refreshing || loading}
        >
          <span aria-hidden="true">↻</span> {refreshing ? 'Actualizando…' : 'Actualizar'}
        </button>
      </section>

      {notice && <div className="notice success-notice" role="status">{notice}</div>}
      {loadError && (
        <div className="notice error-notice" role="alert">
          <span>{loadError}</span>
          <button type="button" className="text-button" onClick={() => void loadItems()}>Reintentar</button>
        </div>
      )}

      <section className="summary-row" aria-label="Resumen del inventario">
        <div className="summary-card">
          <span className="summary-icon blue" aria-hidden="true">▦</span>
          <div><span>Artículos activos</span><strong>{loading ? '—' : activeItems.length}</strong></div>
        </div>
        <div className="summary-card">
          <span className="summary-icon amber" aria-hidden="true">!</span>
          <div><span>Revisar existencias</span><strong>{loading ? '—' : lowStockCount}</strong></div>
        </div>
        <div className="summary-note">Los artículos inactivos y su historial se conservan en el sistema.</div>
      </section>

      <section className="inventory-panel" aria-labelledby="inventory-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">CATÁLOGO</p>
            <h2 id="inventory-title">Artículos</h2>
          </div>
          <label className="search-box">
            <span aria-hidden="true">⌕</span>
            <span className="sr-only">Buscar por código o nombre</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar código o nombre"
            />
          </label>
        </div>

        {loading ? (
          <div className="empty-state" role="status"><span className="loader" /> Cargando artículos…</div>
        ) : !loadError && activeItems.length === 0 ? (
          <div className="empty-state"><span className="empty-icon">▦</span><strong>Aún no hay artículos</strong><span>Crea el primer artículo con el formulario de abajo.</span></div>
        ) : !loadError && visibleItems.length === 0 ? (
          <div className="empty-state">No hay artículos que coincidan con «{search}».</div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Artículo</th>
                  <th scope="col">Unidad</th>
                  <th scope="col">Disponible</th>
                  <th scope="col">Mínimo</th>
                  <th scope="col">Estado</th>
                  <th scope="col" className="actions-heading">Movimiento</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => {
                  const status = stockStatus(item)
                  const movementOpen = activeMovement?.itemId === item.id
                  return (
                    <tr key={item.id}>
                      <td data-label="Artículo">
                        <button className="item-open" type="button" onClick={() => { setNotice(''); setSelectedItem(item) }} aria-label={`Abrir ficha de ${item.name}`}>
                          <span className="item-avatar" aria-hidden="true">{item.name.slice(0, 1).toLocaleUpperCase('es')}</span>
                          <span><strong>{item.name}</strong><small>{item.code}</small></span>
                        </button>
                      </td>
                      <td data-label="Unidad">{item.unit}</td>
                      <td data-label="Disponible"><strong className="quantity">{item.quantity_available}</strong></td>
                      <td data-label="Mínimo">{item.minimum_stock} <span className="muted">{item.unit}</span></td>
                      <td data-label="Estado"><span className={`status-badge ${status.className}`}><span />{status.label}</span></td>
                      <td data-label="Movimiento">
                        <div className="row-actions">
                          <button className="button button-in" type="button" onClick={() => openMovement(item.id, 'in')}>＋ Entrada</button>
                          <button className="button button-out" type="button" onClick={() => openMovement(item.id, 'out')}>− Salida</button>
                        </div>
                        {movementOpen && (
                          <form className="movement-form" onSubmit={submitMovement}>
                            <div className="movement-form-heading">
                              <strong>{activeMovement.direction === 'in' ? 'Registrar entrada' : 'Registrar salida'}</strong>
                              <button type="button" className="close-button" aria-label="Cerrar formulario" onClick={() => setActiveMovement(null)}>×</button>
                            </div>
                            <div className="movement-fields">
                              <label>Cantidad
                                <input name="quantity" type="number" min="1" step="1" required autoFocus />
                              </label>
                              <label>Nota <span className="muted">(opcional)</span>
                                <input name="note" type="text" placeholder="Motivo o referencia" />
                              </label>
                            </div>
                            {actionError && <p className="form-error" role="alert">{actionError}</p>}
                            <div className="form-actions">
                              <button type="button" className="text-button" onClick={() => setActiveMovement(null)}>Cancelar</button>
                              <button type="submit" className="button button-primary" disabled={saving}>{saving ? 'Guardando…' : 'Confirmar movimiento'}</button>
                            </div>
                          </form>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="table-footer"><span>Mostrando solo artículos activos</span><span>{visibleItems.length} {visibleItems.length === 1 ? 'resultado' : 'resultados'}</span></div>
      </section>

      <section className="create-panel" aria-labelledby="create-title">
        <div className="create-intro">
          <span className="create-icon" aria-hidden="true">＋</span>
          <div><p className="eyebrow">AMPLÍA TU CATÁLOGO</p><h2 id="create-title">Nuevo artículo</h2><p>El stock disponible comienza en 0. El mínimo se puede ajustar por artículo.</p></div>
        </div>
        <form className="create-form" onSubmit={submitNewItem}>
          <label>Código
            <input name="code" type="text" maxLength={50} required placeholder="Ej. FIL-001" />
            <small>Máximo 50 caracteres</small>
          </label>
          <label>Nombre
            <input name="name" type="text" maxLength={100} required placeholder="Nombre del repuesto" />
            <small>Máximo 100 caracteres</small>
          </label>
          <label>Unidad
            <input name="unit" type="text" maxLength={20} required placeholder="ud, caja, litro…" />
            <small>Máximo 20 caracteres</small>
          </label>
          <label>Stock mínimo
            <input name="minimum_stock" type="number" min="0" step="1" defaultValue="1" required />
            <small>Entero igual o mayor que 0</small>
          </label>
          {createError && <p className="form-error create-error" role="alert">{createError}</p>}
          <div className="create-submit"><button className="button button-primary" type="submit" disabled={creating}>{creating ? 'Creando…' : 'Crear artículo'}</button></div>
        </form>
      </section>

      <footer className="page-footer"><span>Taller Stock</span><span>Los movimientos actualizan el inventario desde la API.</span></footer>
      {selectedItem && (
        <ItemDetailModal
          key={selectedItem.id}
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onUpdated={syncItem}
        />
      )}
    </main>
  )
}

export default App
