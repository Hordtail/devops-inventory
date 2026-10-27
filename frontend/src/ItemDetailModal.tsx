import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  getItem,
  getItemMovements,
  itemImageUrl,
  registerMovement,
  updateItem,
  uploadItemImage,
  type Item,
  type StockMovement,
} from './api'

type Tab = 'details' | 'history'
type MovementDirection = 'in' | 'out'
const PAGE_SIZE = 50
const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif'])

function stockStatus(item: Item) {
  if (item.quantity_available === 0) return { label: 'Sin stock', tone: 'empty' }
  if (item.quantity_available <= item.minimum_stock) return { label: 'Stock bajo', tone: 'low' }
  return { label: 'Stock suficiente', tone: 'good' }
}

type Props = {
  item: Item
  onClose: () => void
  onUpdated: (item: Item) => void
}

export default function ItemDetailModal({ item: initialItem, onClose, onUpdated }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const previewRef = useRef<string | null>(null)
  const [item, setItem] = useState(initialItem)
  const [tab, setTab] = useState<Tab>('details')
  const [loadingItem, setLoadingItem] = useState(true)
  const [detailError, setDetailError] = useState('')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [movementDirection, setMovementDirection] = useState<MovementDirection | null>(null)
  const [movementSaving, setMovementSaving] = useState(false)
  const [history, setHistory] = useState<StockMovement[]>([])
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historyHasMore, setHistoryHasMore] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => {
      if (dialog?.open) dialog.close()
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void getItem(initialItem.id)
        .then((freshItem) => {
          setItem(freshItem)
          onUpdated(freshItem)
          setDetailError('')
        })
        .catch((error: unknown) => {
          setDetailError(error instanceof Error ? error.message : 'No se pudo cargar la ficha.')
        })
        .finally(() => setLoadingItem(false))
    }, 0)
    return () => window.clearTimeout(timer)
  }, [initialItem.id, onUpdated])

  useEffect(() => () => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current)
  }, [])

  async function refreshItem() {
    const freshItem = await getItem(item.id)
    setItem(freshItem)
    onUpdated(freshItem)
    return freshItem
  }

  async function loadHistory(offset: number, append: boolean) {
    setHistoryLoading(true)
    setDetailError('')
    try {
      const page = await getItemMovements(item.id, offset, PAGE_SIZE)
      setHistory((current) => append ? [...current, ...page] : page)
      setHistoryOffset(offset + page.length)
      setHistoryHasMore(page.length === PAGE_SIZE)
      setHistoryLoaded(true)
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'No se pudo cargar el historial.')
    } finally {
      setHistoryLoading(false)
    }
  }

  async function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const minimumStock = Number(data.get('minimum_stock'))
    if (!Number.isSafeInteger(minimumStock) || minimumStock < 0) {
      setDetailError('El stock mínimo debe ser un entero igual o mayor que cero.')
      return
    }
    setSaving(true)
    setDetailError('')
    setNotice('')
    try {
      const updated = await updateItem(item.id, {
        code: String(data.get('code') ?? '').trim(),
        name: String(data.get('name') ?? '').trim(),
        unit: String(data.get('unit') ?? '').trim(),
        description: String(data.get('description') ?? '').trim() || null,
        active: data.get('active') === 'on',
        minimum_stock: minimumStock,
      })
      setItem(updated)
      onUpdated(updated)
      setEditing(false)
      setNotice('Cambios guardados correctamente.')
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'No se pudieron guardar los cambios.')
    } finally {
      setSaving(false)
    }
  }

  function selectImage(file?: File) {
    if (!file) return
    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      setDetailError('Elige una imagen JPEG, PNG, WebP o GIF.')
      return
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setDetailError('La imagen no puede superar los 5 MiB.')
      return
    }
    if (previewRef.current) URL.revokeObjectURL(previewRef.current)
    const preview = URL.createObjectURL(file)
    previewRef.current = preview
    setPreviewUrl(preview)
    setImageFile(file)
    setDetailError('')
    setNotice('')
  }

  async function submitImage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!imageFile) return
    setUploading(true)
    setDetailError('')
    setNotice('')
    try {
      const updated = await uploadItemImage(item.id, imageFile)
      setItem(updated)
      onUpdated(updated)
      setImageFile(null)
      setPreviewUrl(null)
      if (previewRef.current) URL.revokeObjectURL(previewRef.current)
      previewRef.current = null
      if (fileInputRef.current) fileInputRef.current.value = ''
      setNotice(`Imagen de ${updated.name} actualizada.`)
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'No se pudo subir la imagen.')
    } finally {
      setUploading(false)
    }
  }

  async function submitMovement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    if (!movementDirection) return
    const data = new FormData(form)
    const quantity = Number(data.get('quantity'))
    if (!Number.isSafeInteger(quantity) || quantity <= 0) {
      setDetailError('La cantidad debe ser un número entero mayor que cero.')
      return
    }
    setMovementSaving(true)
    setDetailError('')
    setNotice('')
    try {
      await registerMovement(item.id, movementDirection, {
        quantity,
        ...(String(data.get('note') ?? '').trim()
          ? { note: String(data.get('note')).trim() }
          : {}),
      })
      setMovementDirection(null)
      form.reset()
      setNotice(`${movementDirection === 'in' ? 'Entrada' : 'Salida'} registrada para ${item.name}.`)
      let refreshFailed = false
      try {
        await refreshItem()
      } catch {
        refreshFailed = true
      }
      if (tab === 'history') await loadHistory(0, false)
      if (refreshFailed) {
        setDetailError('El movimiento se registró, pero no se pudo actualizar la ficha. Vuelve a intentarlo.')
      }
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'No se pudo registrar el movimiento.')
    } finally {
      setMovementSaving(false)
    }
  }

  const status = stockStatus(item)
  const imageUrl = previewUrl ?? itemImageUrl(item)

  return (
    <dialog
      ref={dialogRef}
      className="detail-dialog"
      aria-labelledby="detail-dialog-title"
      onClose={onClose}
    >
      <div className="detail-modal">
        <header className="detail-header">
          <div className="detail-title-block">
            <span className="detail-kicker">FICHA DE ARTÍCULO</span>
            <h2 id="detail-dialog-title">{item.name}</h2>
            <span className="detail-code">{item.code}</span>
          </div>
          <button className="modal-close" type="button" aria-label="Cerrar ficha" onClick={() => dialogRef.current?.close()}>×</button>
        </header>

        <div className="detail-tabs" role="tablist" aria-label="Secciones de la ficha">
          <button type="button" role="tab" aria-selected={tab === 'details'} className={tab === 'details' ? 'selected' : ''} onClick={() => setTab('details')}>Detalles</button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'history'}
            className={tab === 'history' ? 'selected' : ''}
            onClick={() => {
              setTab('history')
              if (!historyLoaded) void loadHistory(0, false)
            }}
          >
            Historial <span className="history-count">{history.length || ''}</span>
          </button>
        </div>

        {notice && <div className="modal-notice" role="status">{notice}</div>}
        {detailError && <div className="modal-error" role="alert">{detailError}</div>}
        {loadingItem ? (
          <div className="modal-loading" role="status">Cargando ficha…</div>
        ) : tab === 'details' ? (
          <section className="detail-content" role="tabpanel" aria-label="Detalles">
            <div className="detail-top-grid">
              <div className="image-column">
                <div className={`item-image-frame ${imageUrl ? '' : 'no-image'}`}>
                  {imageUrl
                    ? <img src={imageUrl} alt={`Imagen de ${item.name}`} />
                    : <div className="no-image-placeholder"><span aria-hidden="true">▧</span><strong>Sin imagen</strong><small>Añade una foto del artículo</small></div>}
                </div>
                <form className="image-upload-form" onSubmit={submitImage}>
                  <label className="file-picker">
                    <span>Seleccionar imagen</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      onChange={(event) => selectImage(event.currentTarget.files?.[0])}
                    />
                  </label>
                  <small>JPEG, PNG, WebP o GIF · máximo 5 MiB</small>
                  <button className="button button-primary" type="submit" disabled={!imageFile || uploading}>
                    {uploading ? 'Subiendo…' : 'Subir imagen'}
                  </button>
                </form>
              </div>

              <div className="details-column">
                <div className="stock-summary-detail">
                  <div><span>Disponible</span><strong>{item.quantity_available} <small>{item.unit}</small></strong></div>
                  <div><span>Stock mínimo</span><strong>{item.minimum_stock} <small>{item.unit}</small></strong></div>
                  <span className={`status-badge ${status.tone}`}><span />{status.label}</span>
                </div>

                {editing ? (
                  <form className="item-edit-form" onSubmit={saveDetails}>
                    <div className="edit-form-heading"><strong>Editar datos</strong><span>Los campos con * son obligatorios</span></div>
                    <label>Código *<input name="code" defaultValue={item.code} maxLength={50} required /></label>
                    <label>Nombre *<input name="name" defaultValue={item.name} maxLength={100} required /></label>
                    <label>Unidad *<input name="unit" defaultValue={item.unit} maxLength={20} required /></label>
                    <label>Stock mínimo<input name="minimum_stock" type="number" min="0" step="1" defaultValue={item.minimum_stock} required /></label>
                    <label className="description-field">Descripción<textarea name="description" defaultValue={item.description ?? ''} maxLength={4000} rows={4} placeholder="Detalles útiles para identificar el artículo" /></label>
                    <label className="active-toggle"><input name="active" type="checkbox" defaultChecked={item.active} /> Artículo activo</label>
                    <div className="modal-form-actions">
                      <button type="button" className="text-button" onClick={() => setEditing(false)}>Cancelar</button>
                      <button type="submit" className="button button-primary" disabled={saving}>{saving ? 'Guardando…' : 'Guardar cambios'}</button>
                    </div>
                  </form>
                ) : (
                  <div className="item-readonly-details">
                    <div className="readonly-title"><strong>Descripción</strong><button type="button" className="text-button" onClick={() => { setDetailError(''); setEditing(true) }}>Editar datos</button></div>
                    <p>{item.description || <span className="empty-description">Sin descripción</span>}</p>
                    <dl>
                      <div><dt>Código</dt><dd>{item.code}</dd></div>
                      <div><dt>Unidad</dt><dd>{item.unit}</dd></div>
                      <div><dt>Estado</dt><dd>{item.active ? 'Activo' : 'Inactivo'}</dd></div>
                    </dl>
                  </div>
                )}

                <div className="modal-movement-block">
                  <div className="modal-movement-actions">
                    <strong>Actualizar existencias</strong>
                    <div>
                      <button className="button button-in" type="button" onClick={() => { setMovementDirection('in'); setDetailError('') }}>＋ Entrada</button>
                      <button className="button button-out" type="button" onClick={() => { setMovementDirection('out'); setDetailError('') }}>− Salida</button>
                    </div>
                  </div>
                  {movementDirection && (
                    <form className="modal-movement-form" onSubmit={submitMovement}>
                      <div className="modal-movement-form-title">
                        <strong>Registrar {movementDirection === 'in' ? 'entrada' : 'salida'}</strong>
                        <button type="button" className="icon-close" aria-label="Cancelar movimiento" onClick={() => setMovementDirection(null)}>×</button>
                      </div>
                      <div className="modal-movement-fields">
                        <label>Cantidad<input name="quantity" type="number" min="1" step="1" required autoFocus /></label>
                        <label>Nota <span>(opcional)</span><input name="note" maxLength={2000} placeholder="Motivo o referencia" /></label>
                      </div>
                      <div className="modal-form-actions">
                        <button type="button" className="text-button" onClick={() => setMovementDirection(null)}>Cancelar</button>
                        <button type="submit" className="button button-primary" disabled={movementSaving}>{movementSaving ? 'Guardando…' : 'Confirmar'}</button>
                      </div>
                    </form>
                  )}
                </div>
              </div>
            </div>
          </section>
        ) : (
          <section className="history-content" role="tabpanel" aria-label="Historial">
            {historyLoading && history.length === 0 ? (
              <div className="modal-loading" role="status">Cargando movimientos…</div>
            ) : history.length === 0 ? (
              <div className="history-empty"><span aria-hidden="true">↕</span><strong>Aún no hay movimientos</strong><small>Las entradas y salidas registradas aparecerán aquí.</small></div>
            ) : (
              <>
                <div className="history-intro"><strong>Movimientos de stock</strong><span>Más recientes primero</span></div>
                <ol className="movement-history">
                  {history.map((movement) => (
                    <li key={movement.id} className={`history-row ${movement.movement_type === 'IN' ? 'history-in' : 'history-out'}`}>
                      <span className="history-symbol" aria-hidden="true">{movement.movement_type === 'IN' ? '＋' : '−'}</span>
                      <div className="history-main">
                        <strong>{movement.movement_type === 'IN' ? 'Entrada' : 'Salida'} <span>· {movement.quantity} {item.unit}</span></strong>
                        <small>{new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(movement.occurred_at))}</small>
                        {movement.note && <p>{movement.note}</p>}
                      </div>
                      <span className="history-id">#{movement.id}</span>
                    </li>
                  ))}
                </ol>
                {historyHasMore && (
                  <button className="button button-secondary load-more" type="button" disabled={historyLoading} onClick={() => void loadHistory(historyOffset, true)}>
                    {historyLoading ? 'Cargando…' : 'Cargar movimientos anteriores'}
                  </button>
                )}
              </>
            )}
          </section>
        )}
      </div>
    </dialog>
  )
}
