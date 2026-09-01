import { useEffect, useState } from 'react'

export const Modal = ({ open, title, onClose, children, width = 'max-w-lg' }) => {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/80 p-6 backdrop-blur-sm"
         onClick={onClose}>
      <div className={`mt-12 w-full ${width} rounded-xl border border-slate-800 bg-slate-900 p-6`}
           onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-medium text-slate-100">{title}</h3>
          <button onClick={onClose}
            className="rounded px-2 text-slate-500 hover:text-slate-300">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export const Field = ({ label, children, hint }) => (
  <div>
    <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
      {label}
    </label>
    {children}
    {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
  </div>
)

const inputCls =
  'w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm ' +
  'text-slate-100 outline-none focus:border-emerald-600'

export const Input = (props) => <input {...props} className={inputCls} />

export const Select = ({ options, ...props }) => (
  <select {...props} className={inputCls}>
    {options.map((o) =>
      typeof o === 'string'
        ? <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>
        : <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
)

export const Btn = ({ variant = 'primary', className = '', ...props }) => {
  const styles = {
    primary: 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950',
    ghost: 'border border-slate-700 text-slate-300 hover:bg-slate-800',
    danger: 'border border-rose-800 text-rose-300 hover:bg-rose-950/40',
  }
  return (
    <button {...props}
      className={`rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40 ${styles[variant]} ${className}`} />
  )
}

export function useForm(initial) {
  const [values, setValues] = useState(initial)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (k) => (e) => {
    const v = e.target.type === 'number'
      ? (e.target.value === '' ? '' : Number(e.target.value))
      : e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setValues((s) => ({ ...s, [k]: v }))
  }

  const submit = (fn) => async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await fn(values)
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setSaving(false)
    }
  }

  return { values, setValues, set, submit, error, setError, saving,
           reset: () => { setValues(initial); setError(null) } }
}

export const FormError = ({ message }) =>
  message ? (
    <p className="rounded border border-rose-900/60 bg-rose-950/30 px-3 py-2 text-sm text-rose-300">
      {message}
    </p>
  ) : null

export const Toolbar = ({ children }) => (
  <div className="mb-4 flex flex-wrap items-center gap-2">{children}</div>
)

export const SearchInput = ({ value, onChange, placeholder = 'Search…' }) => (
  <input value={value} onChange={onChange} placeholder={placeholder}
    className="w-56 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100 outline-none focus:border-emerald-600" />
)

export const FilterSelect = ({ value, onChange, options, placeholder }) => (
  <select value={value} onChange={onChange}
    className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-emerald-600">
    <option value="">{placeholder}</option>
    {options.map((o) => (
      <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>
    ))}
  </select>
)

export const PageHeader = ({ title, subtitle, action }) => (
  <div className="mb-6 flex items-start justify-between">
    <div>
      <h2 className="text-2xl font-semibold">{title}</h2>
      {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
    </div>
    {action}
  </div>
)
